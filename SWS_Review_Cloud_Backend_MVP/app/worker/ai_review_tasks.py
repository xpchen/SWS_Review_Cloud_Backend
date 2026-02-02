"""
AI审查任务：按checkpoint分章节审查，证据校验，结构化输出
"""
import json
import logging
import re
from .. import db
from ..settings import settings
from ..services.review_run_service import get_review_run, update_run_status, insert_issue
from ..ai.rag import search_chunks
from ..ai.prompts import build_review_messages
from ..ai.qwen_client import chat_json
from .app import app

_schema = settings.DB_SCHEMA
logger = logging.getLogger(__name__)


def _execute_ai_review(version_id: int, run_id: int):
    """
    执行AI审查的核心逻辑（不依赖Celery装饰器）
    
    Args:
        version_id: 版本ID
        run_id: 审查运行ID
    """
    run = get_review_run(run_id)
    if not run or run["version_id"] != version_id:
        return
    
    update_run_status(run_id, "RUNNING", progress=0)
    
    # 获取所有AI类型的checkpoint
    # 检查字段是否存在，向后兼容旧schema
    try:
        # 尝试查询包含新字段的完整查询
        checkpoints = db.fetch_all(
            f"""
            SELECT id, code, name, category, review_category, engine_type, target_outline_prefix, prompt_template, rule_config_json
            FROM {_schema}.review_checkpoint
            WHERE enabled = true
            AND (engine_type = 'AI' OR (engine_type IS NULL AND category = 'AI'))
            ORDER BY order_index NULLS LAST, id
            """,
            {}
        )
    except Exception as e:
        # 如果字段不存在，使用兼容旧schema的查询
        if "review_category" in str(e) or "engine_type" in str(e):
            logger.warning("新字段不存在，使用兼容旧schema的查询。请执行迁移006_checkpoint_schema_refactor.sql")
            checkpoints = db.fetch_all(
                f"""
                SELECT id, code, name, category, category as review_category, 
                       CASE WHEN category = 'AI' THEN 'AI' ELSE 'RULE' END as engine_type,
                       target_outline_prefix, prompt_template, rule_config_json
                FROM {_schema}.review_checkpoint
                WHERE enabled = true
                AND category = 'AI'
                ORDER BY order_index NULLS LAST, id
                """,
                {}
            )
        else:
            raise
    
    if not checkpoints:
        logger.warning(f"No AI checkpoints found for version {version_id}")
        update_run_status(run_id, "DONE", progress=100)
        return
    
    total_checkpoints = len(checkpoints)
    total_issues = 0
    
    for idx, checkpoint in enumerate(checkpoints):
        checkpoint_code = checkpoint["code"]
        checkpoint_name = checkpoint["name"]
        target_prefix = checkpoint.get("target_outline_prefix")
        prompt_template = checkpoint.get("prompt_template") or ""
        rule_config = checkpoint.get("rule_config_json") or {}
        
        logger.info(f"Processing checkpoint {checkpoint_code} ({idx+1}/{total_checkpoints})")
        
        try:
            issues = _run_checkpoint_ai_review(
                version_id=version_id,
                checkpoint_code=checkpoint_code,
                checkpoint_name=checkpoint_name,
                target_prefix=target_prefix,
                prompt_template=prompt_template,
                rule_config=rule_config,
            )
            
            # 插入问题
            for issue in issues:
                insert_issue(
                    version_id=version_id,
                    run_id=run_id,
                    issue_type=issue.get("issue_type", "AI_COMPLIANCE_GAP"),
                    severity=issue.get("severity", "S2"),
                    title=issue.get("title", "AI审查发现问题"),
                    description=issue.get("description", ""),
                    suggestion=issue.get("suggestion", ""),
                    confidence=float(issue.get("confidence", 0.5)),
                    page_no=issue.get("page_no", 1),
                    evidence_block_ids=issue.get("evidence_block_ids", []),
                    evidence_quotes=issue.get("evidence_quotes", []),
                    anchor_rects=issue.get("anchor_rects"),
                    checkpoint_code=checkpoint_code,
                )
                total_issues += 1
            
            progress = int((idx + 1) / total_checkpoints * 100)
            update_run_status(run_id, "RUNNING", progress=progress)
            
        except Exception as e:
            logger.error(f"Error processing checkpoint {checkpoint_code}: {e}", exc_info=True)
            # 继续处理下一个checkpoint
            continue
    
    update_run_status(run_id, "DONE", progress=100)
    logger.info(f"AI review completed: {total_issues} issues found")


@app.task(bind=True)
def run_ai_review_task(self, version_id: int, run_id: int):
    """Celery任务包装器"""
    _execute_ai_review(version_id, run_id)


def _run_checkpoint_ai_review(
    version_id: int,
    checkpoint_code: str,
    checkpoint_name: str,
    target_prefix: str | None,
    prompt_template: str,
    rule_config: dict,
) -> list[dict]:
    """
    执行单个checkpoint的AI审查
    
    返回：结构化问题列表
    """
    # 1. 获取目标章节的blocks
    blocks = _get_target_blocks(version_id, target_prefix)
    
    if not blocks:
        logger.warning(f"No blocks found for checkpoint {checkpoint_code} with prefix {target_prefix}")
        return []
    
    # 2. 构建上下文（限制长度）
    context = _build_context(blocks, max_length=rule_config.get("max_context_length", 8000))
    
    # 3. 检索相关规范条款
    kb_keywords = rule_config.get("kb_keywords", checkpoint_name)
    kb_refs = rule_config.get("kb_refs", [])
    norm_chunks = _search_norm_chunks(kb_keywords, kb_refs, top_k=rule_config.get("top_k", 5))
    
    # 4. 构建prompt
    messages = build_review_messages(
        section_context=context,
        norm_chunks=norm_chunks,
        checkpoint_name=checkpoint_name,
        prompt_template=prompt_template,
    )
    
    # 5. 调用AI
    try:
        out = chat_json(messages)
    except Exception as e:
        logger.error(f"AI call failed for checkpoint {checkpoint_code}: {e}")
        return []
    
    # 6. 验证和规范化输出
    issues = out.get("issues") or []
    validated_issues = []
    
    valid_chunk_ids = {c["id"] for c in norm_chunks}
    blocks_by_id = {b["id"]: b for b in blocks}
    
    for item in issues:
        validated = _validate_issue(item, blocks_by_id, valid_chunk_ids)
        if validated:
            validated_issues.append(validated)
    
    return validated_issues


def _get_target_blocks(version_id: int, target_prefix: str | None) -> list[dict]:
    """
    根据target_outline_prefix获取目标章节的blocks
    
    target_prefix格式：如"1.2"表示只取1.2章节及其子章节
    """
    if not target_prefix:
        # 没有指定前缀，返回所有段落块
        return db.fetch_all(
            f"""
            SELECT b.id, b.text, b.order_index, b.outline_node_id, b.block_type
            FROM {_schema}.doc_block b
            WHERE b.version_id = %(v)s
            AND b.block_type IN ('PARA', 'HEADING')
            AND b.text IS NOT NULL
            ORDER BY b.order_index
            """,
            {"v": version_id}
        )
    
    # 查找匹配的outline节点
    outline_nodes = db.fetch_all(
        f"""
        SELECT id, node_no, title
        FROM {_schema}.doc_outline_node
        WHERE version_id = %(v)s
        AND (node_no LIKE %(prefix)s OR node_no = %(prefix_exact)s)
        ORDER BY order_index
        """,
        {"v": version_id, "prefix": f"{target_prefix}.%", "prefix_exact": target_prefix}
    )
    
    if not outline_nodes:
        return []
    
    outline_ids = [n["id"] for n in outline_nodes]
    
    # 获取这些节点下的blocks
    return db.fetch_all(
        f"""
        SELECT b.id, b.text, b.order_index, b.outline_node_id, b.block_type
        FROM {_schema}.doc_block b
        WHERE b.version_id = %(v)s
        AND b.outline_node_id = ANY(%(ids)s)
        AND b.block_type IN ('PARA', 'HEADING')
        AND b.text IS NOT NULL
        ORDER BY b.order_index
        """,
        {"v": version_id, "ids": outline_ids}
    )


def _build_context(blocks: list[dict], max_length: int = 8000) -> str:
    """
    构建上下文文本，限制长度
    每个block前标注block_id，便于AI引用
    """
    parts = []
    current_length = 0
    
    for block in blocks:
        text = (block.get("text") or "").strip()
        if not text:
            continue
        
        # 限制每个block的长度
        block_text = text[:500] if len(text) > 500 else text
        
        # 标注block_id
        block_id = block.get("id", 0)
        annotated_text = f"[block_id={block_id}]\n{block_text}"
        
        if current_length + len(annotated_text) > max_length:
            break
        
        parts.append(annotated_text)
        current_length += len(annotated_text)
    
    return "\n\n".join(parts)


def _search_norm_chunks(keywords: str, kb_refs: list[str], top_k: int = 5) -> list[dict]:
    """检索规范条款chunks"""
    # 如果指定了kb_refs，优先使用
    if kb_refs:
        # 按refs搜索
        chunks = []
        for ref in kb_refs[:top_k]:
            ref_chunks = search_chunks(ref, top_k=1)
            chunks.extend(ref_chunks)
        return chunks[:top_k]
    
    # 否则用关键词搜索
    return search_chunks(keywords, top_k=top_k)


def _validate_issue(
    item: dict,
    blocks_by_id: dict[int, dict],
    valid_chunk_ids: set[int],
) -> dict | None:
    """
    验证AI输出的issue，确保：
    1. evidence中的block_id存在
    2. quote必须是block.text的子串
    3. norm_refs中的kb_chunk_id必须有效
    """
    evidence = item.get("evidence") or []
    if not evidence:
        return None  # 没有证据，丢弃
    
    validated_evidence = []
    evidence_block_ids = []
    
    for ev in evidence:
        block_id = ev.get("block_id")
        quote = ev.get("quote", "").strip()
        
        if not block_id or block_id not in blocks_by_id:
            continue  # block_id无效，跳过这条证据
        
        block = blocks_by_id[block_id]
        block_text = block.get("text") or ""
        
        # 验证quote是否是block_text的子串（允许部分匹配）
        if quote:
            # 去除空格和标点后匹配
            quote_clean = re.sub(r"[\s，,。.；;：:]", "", quote)
            block_text_clean = re.sub(r"[\s，,。.；;：:]", "", block_text)
            
            if quote_clean and quote_clean not in block_text_clean:
                # quote不匹配，降级置信度或跳过
                logger.warning(f"Quote mismatch for block {block_id}: '{quote[:50]}' not in block text")
                continue
        
        validated_evidence.append({
            "block_id": block_id,
            "page_no": ev.get("page_no"),  # 不设置默认值，让insert_issue从evidence_block_ids反查
            "quote": quote[:200] if quote else "",  # 限制quote长度
        })
        evidence_block_ids.append(block_id)
    
    if not validated_evidence:
        return None  # 所有证据都无效，丢弃
    
    # 验证norm_refs
    norm_refs = item.get("norm_refs") or []
    validated_norm_refs = []
    for nr in norm_refs:
        kb_chunk_id = nr.get("kb_chunk_id")
        if kb_chunk_id and kb_chunk_id in valid_chunk_ids:
            validated_norm_refs.append({
                "kb_chunk_id": kb_chunk_id,
                "ref": nr.get("ref", ""),
                "quote": nr.get("quote", "")[:200],
            })
    
    # 构建验证后的issue
    # page_no设为None，让insert_issue从evidence_block_ids反查
    return {
        "issue_type": item.get("issue_type", "AI_COMPLIANCE_GAP"),
        "severity": item.get("severity", "S2"),
        "title": item.get("title", "AI审查发现问题")[:255],
        "description": item.get("description", "")[:2000],
        "suggestion": item.get("suggestion", "")[:2000],
        "confidence": max(0.0, min(1.0, float(item.get("confidence", 0.5)))),
        "page_no": None,  # 不设置默认值，让insert_issue从evidence_block_ids反查
        "evidence_block_ids": evidence_block_ids[:10],  # 最多10个证据块
        "evidence_quotes": validated_evidence,
        "anchor_rects": None,  # 可以后续从block_page_anchor获取
    }
