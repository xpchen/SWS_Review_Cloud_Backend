"""
AI 审查任务：全部使用规则校验引擎（AI），基于文档内容与规范库输出校验结果。
- 单次请求最多重试 3 次后视为失败
- 允许 2～3 批并发请求
- 失败的批次规则重新加入处理队列再跑一轮
"""
import json
import logging
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from .. import db
from ..settings import settings
from ..services.review_run_service import get_review_run, update_run_status, insert_issue
from ..ai.rule_engine_prompt import load_norm_lib, get_rule_batches, build_rule_engine_messages_batch
from ..ai.qwen_client import chat_json
from .app import app

_schema = settings.DB_SCHEMA
logger = logging.getLogger(__name__)

# 单次请求最多重试次数，超过则视为该批失败
MAX_REQUEST_RETRIES = 3
# 并发批次数（2～3）
CONCURRENT_BATCHES = 3

# 问题类型枚举（AI/用户） -> 库内 issue_type（含 sum_check_row/col、percentage_sum、punctuation、missing_section、ai_gap 等）
ISSUE_TYPE_MAP = {
    "一致性": "CONSISTENCY",
    "格式": "FORMAT",
    "表内计算": "SUM_MISMATCH_ROW",
    "合计行": "SUM_MISMATCH_ROW",
    "合计列": "SUM_MISMATCH_COL",
    "百分比合计": "PERCENTAGE_SUM_MISMATCH",
    "业务逻辑": "BUSINESS_LOGIC",
    "规范引用": "CONTENT",
    "信息缺失": "MISSING_SECTION",
    "术语规范": "FORMAT",
    "标点": "FORMAT",
    "缺失章节": "MISSING_SECTION",
    "单位不一致": "UNIT_INCONSISTENT",
    "公式平衡": "FORMULA_BALANCE_MISMATCH",
    "AI合规差距": "AI_COMPLIANCE_GAP",
}

# review_type（规范库）-> 统计用 形式/技术；形式审查=FORMAT+CONTENT 等，技术审查=其余
REVIEW_TYPE_FORM_TECH = ("FORM", "TECH")
FORM_REVIEW_TYPES = frozenset({"FORMAT", "CONTENT"})

# 严重程度（用户） -> 库内 severity
SEVERITY_MAP = {
    "致命": "S1",
    "高": "S2",
    "中": "S3",
    "低": "INFO",
}


def _run_one_batch_with_retries(doc_content: str, rules_batch: list, batch_index: int, total_batches: int):
    """
    执行单批 AI 请求，最多重试 MAX_REQUEST_RETRIES 次。
    返回 (rules_batch, out_dict or None)，失败时 out 为 None。
    """
    messages = build_rule_engine_messages_batch(
        doc_content, rules_batch, batch_index, total_batches
    )
    for attempt in range(MAX_REQUEST_RETRIES):
        try:
            out = chat_json(messages)
            return (rules_batch, out)
        except Exception as e:
            logger.warning(
                f"AI batch {batch_index + 1}/{total_batches} attempt {attempt + 1}/{MAX_REQUEST_RETRIES} failed: {e}"
            )
    return (rules_batch, None)


def _process_batch_result(out, blocks, version_id, run_id, rules_batch: list[dict]):
    """解析单批 AI 返回的 JSON，写入 issues 表；review_type 来自本批规则，用于形式/技术统计。返回本批写入条数。"""
    raw_issues = out.get("规则校验结果") or out.get("issues") or []
    if not isinstance(raw_issues, list):
        raw_issues = []
    rule_by_id = {r.get("rule_id"): r for r in (rules_batch or []) if r.get("rule_id")}
    count = 0
    for item in raw_issues:
        try:
            rule_id = (item.get("rule_definition") or {}).get("rule_id") or item.get("checkpoint_code")
            rule = rule_by_id.get(rule_id) if rule_id else None
            mapped = _map_engine_issue_to_db(item, blocks, rule=rule)
            if not mapped:
                continue
            insert_issue(
                version_id=version_id,
                run_id=run_id,
                issue_type=mapped["issue_type"],
                severity=mapped["severity"],
                title=mapped["title"],
                description=mapped["description"],
                suggestion=mapped["suggestion"],
                confidence=mapped.get("confidence", 0.7),
                page_no=mapped.get("page_no"),
                evidence_block_ids=mapped.get("evidence_block_ids") or [],
                evidence_quotes=mapped.get("evidence_quotes") or [],
                anchor_rects=None,
                checkpoint_code=mapped.get("checkpoint_code"),
                review_type=mapped.get("review_type"),
            )
            count += 1
        except Exception as e:
            logger.warning(f"Skip issue item: {e}", exc_info=False)
    return count


def _execute_ai_review(version_id: int, run_id: int):
    """
    执行 AI 规则校验：按批请求，每批 5～7 条规则；单次请求最多重试 3 次；
    允许 2～3 批并发；失败批次的规则重新入队再跑一轮。
    """
    run = get_review_run(run_id)
    if not run or run["version_id"] != version_id:
        return

    update_run_status(run_id, "RUNNING", progress=0)

    blocks = _get_all_blocks_with_page(version_id)
    if not blocks:
        logger.warning(f"No blocks found for version {version_id}")
        update_run_status(run_id, "DONE", progress=100)
        return

    doc_content = _build_doc_content(blocks)
    norm_lib = load_norm_lib()
    batches = get_rule_batches(norm_lib, batch_size=6)
    total_batches = len(batches)

    if total_batches == 0:
        logger.warning("No rules in norm lib, skip AI review")
        update_run_status(run_id, "DONE", progress=100)
        return

    logger.info(
        f"[版本 {version_id}] 共 {len(norm_lib)} 条规则，分 {total_batches} 批请求（每批 5～7 条），并发 {CONCURRENT_BATCHES} 批"
    )

    total_issues = 0
    failed_rules = []

    def run_round(batches_list: list[list], round_name: str):
        """并发执行多批（最多 CONCURRENT_BATCHES 批同时请求），收集成功条数与失败规则。"""
        nonlocal total_issues
        n_batches = len(batches_list)
        round_issues = 0
        round_failed = []
        completed = 0
        with ThreadPoolExecutor(max_workers=CONCURRENT_BATCHES) as executor:
            futures = {
                executor.submit(
                    _run_one_batch_with_retries,
                    doc_content,
                    rb,
                    batch_index,
                    n_batches,
                ): (batch_index, rb)
                for batch_index, rb in enumerate(batches_list)
            }
            for fut in as_completed(futures):
                batch_index, rules_batch = futures[fut]
                try:
                    _, out = fut.result()
                except Exception as e:
                    logger.error(f"Batch {batch_index + 1} error: {e}", exc_info=True)
                    round_failed.extend(rules_batch)
                    completed += 1
                    update_run_status(run_id, "RUNNING", progress=int(completed / n_batches * 100))
                    continue
                if out is None:
                    round_failed.extend(rules_batch)
                    logger.warning(
                        f"Batch {batch_index + 1}/{n_batches} failed after {MAX_REQUEST_RETRIES} retries"
                    )
                else:
                    cnt = _process_batch_result(out, blocks, version_id, run_id, rules_batch)
                    round_issues += cnt
                    logger.info(
                        f"[版本 {version_id}] {round_name} 第 {batch_index + 1}/{n_batches} 批完成，本批 {cnt} 条结果"
                    )
                completed += 1
                update_run_status(run_id, "RUNNING", progress=int(completed / n_batches * 100))
        total_issues += round_issues
        return round_failed

    failed_rules = run_round(batches, "首轮")

    if failed_rules:
        retry_batches = get_rule_batches(failed_rules, batch_size=6)
        logger.info(f"[版本 {version_id}] 将 {len(failed_rules)} 条失败规则重新入队，分 {len(retry_batches)} 批重试")
        run_round(retry_batches, "重试轮")
        # 若重试轮仍有失败，仅打日志，不再无限重试
        # （run_round 内未把“重试轮”的 failed 再收集，这里如需可再扩展）

    update_run_status(run_id, "DONE", progress=100)
    logger.info(f"AI rule engine review completed: {total_batches} batches, {total_issues} issues found")


@app.task(bind=True)
def run_ai_review_task(self, version_id: int, run_id: int):
    """Celery 任务包装"""
    _execute_ai_review(version_id, run_id)


def _get_all_blocks_with_page(version_id: int) -> list[dict]:
    """获取版本下所有段落/标题块，并尽量带上页码。"""
    blocks = db.fetch_all(
        f"""
        SELECT b.id, b.text, b.order_index, b.outline_node_id, b.block_type
        FROM {_schema}.doc_block b
        WHERE b.version_id = %(v)s
        AND b.block_type IN ('PARA', 'HEADING')
        AND b.text IS NOT NULL
        ORDER BY b.order_index
        """,
        {"v": version_id},
    )
    if not blocks:
        return []
    # 可选：从 doc_block_page_anchor 查页码，简化起见先用 order_index 估算或默认 1
    block_ids = [b["id"] for b in blocks]
    page_by_block = _get_page_by_blocks(version_id, block_ids)
    for b in blocks:
        b["page_no"] = page_by_block.get(b["id"], 1)
    return blocks


def _get_page_by_blocks(version_id: int, block_ids: list[int]) -> dict[int, int]:
    """根据 block 的 page_anchor 查页码。"""
    if not block_ids:
        return {}
    try:
        rows = db.fetch_all(
            f"""
            SELECT block_id, page_no
            FROM {_schema}.doc_block_page_anchor
            WHERE version_id = %(v)s AND block_id = ANY(%(ids)s)
            """,
            {"v": version_id, "ids": block_ids},
        )
        return {r["block_id"]: r["page_no"] for r in rows}
    except Exception:
        return {}


def _build_doc_content(blocks: list[dict], max_chars: int = 100000) -> str:
    """组装文档内容：每段带 [block_id=xx] 与页码，便于 AI 引用。"""
    parts = []
    total = 0
    for b in blocks:
        text = (b.get("text") or "").strip()
        if not text:
            continue
        bid = b.get("id", 0)
        pno = b.get("page_no", 1)
        line = f"[block_id={bid}][page={pno}]\n{text[:2000]}"
        if total + len(line) > max_chars:
            break
        parts.append(line)
        total += len(line)
    return "\n\n".join(parts)


def _map_engine_issue_to_db(item: dict, blocks: list[dict], rule: dict | None = None) -> dict | None:
    """
    将规则引擎输出的一条问题映射为 insert_issue 所需格式。
    - issue_title -> title
    - issue_type -> 一致性/CONSISTENCY 等（含 sum_check_row/col、percentage_sum、punctuation、missing_section、ai_gap）
    - severity -> 致命/S1 等
    - location.page -> page_no
    - evidence.snippets -> evidence_quotes
    - fix_suggestion -> suggestion
    - rule.review_type -> review_type（形式/技术统计用）
    """
    title = (item.get("issue_title") or item.get("title") or "审查发现问题").strip()[:255]
    if not title:
        return None

    raw_type = (item.get("issue_type") or "").strip()
    issue_type = ISSUE_TYPE_MAP.get(raw_type, "AI_COMPLIANCE_GAP")

    raw_sev = (item.get("severity") or "").strip()
    severity = SEVERITY_MAP.get(raw_sev, "S2")

    loc = item.get("location") or {}
    evidence = item.get("evidence") or {}
    page_refs = evidence.get("page_refs") or []
    if isinstance(page_refs, str):
        page_refs = [page_refs]
    # 页码优先：evidence.page_refs[0] -> location.page -> 匹配到的 block.page_no -> 1
    page_no = None
    if page_refs:
        try:
            p = page_refs[0]
            page_no = int(p) if p is not None else None
        except (TypeError, ValueError):
            pass
    if page_no is None:
        page_no = loc.get("page")
    if page_no is not None:
        try:
            page_no = int(page_no)
        except (TypeError, ValueError):
            page_no = None
    if page_no is None and blocks:
        # 用 anchor_text/snippet 匹配到的 block 的 page_no
        snippets = evidence.get("snippets") or []
        anchor_text = (loc.get("anchor_text") or "").strip() or (snippets[0] if snippets else "")
        if anchor_text:
            anchor_clean = re.sub(r"\s+", "", anchor_text)[:50]
            for b in blocks:
                t = (b.get("text") or "").strip()
                if anchor_clean and re.sub(r"\s+", "", t)[:100].find(anchor_clean) >= 0:
                    page_no = b.get("page_no", 1)
                    break
    if page_no is None:
        page_no = 1

    snippets = evidence.get("snippets") or []
    if isinstance(snippets, str):
        snippets = [snippets]
    # evidence_quotes：前端展示用，传字符串列表或 [{"quote": s}]
    evidence_quotes = [s[:500] if isinstance(s, str) else str(s)[:500] for s in snippets[:10]]

    fix = item.get("fix_suggestion") or {}
    if isinstance(fix, str):
        suggestion = fix[:2000]
    else:
        steps = fix.get("fix_steps") or []
        suggested = fix.get("suggested_text") or ""
        suggestion = (suggested + "\n" + "\n".join(steps))[:2000].strip() or "请根据规范库与问题描述自行修正。"

    desc_parts = [item.get("description") or item.get("issue_title") or title]
    rule_def = item.get("rule_definition") or {}
    if rule_def.get("rule_name"):
        desc_parts.append(f"规则：{rule_def.get('rule_name')}")
    norm = item.get("norm_basis") or {}
    if norm.get("basis_text"):
        desc_parts.append(f"依据：{norm.get('basis_text')}")
    description = "\n".join(desc_parts)[:2000]

    # 尝试用 anchor_text 或 snippet 匹配 block_id（用于证据定位；页码已在上面从 page_refs/location/block 取）
    evidence_block_ids = []
    anchor_text = (loc.get("anchor_text") or "").strip() or (snippets[0] if snippets else "")
    if anchor_text:
        anchor_clean = re.sub(r"\s+", "", anchor_text)[:50]
        for b in blocks:
            t = (b.get("text") or "").strip()
            if anchor_clean and re.sub(r"\s+", "", t)[:100].find(anchor_clean) >= 0:
                evidence_block_ids.append(b["id"])
                break
        if not evidence_block_ids and blocks:
            evidence_block_ids.append(blocks[0]["id"])

    # review_type 来自规范库规则，用于按 形式/技术 统计（未来可按 review_type 枚举统计）
    review_type = None
    if rule and isinstance(rule, dict):
        review_type = rule.get("review_type")

    return {
        "issue_type": issue_type,
        "severity": severity,
        "title": title,
        "description": description,
        "suggestion": suggestion,
        "confidence": 0.75,
        "page_no": page_no,
        "evidence_block_ids": evidence_block_ids[:5],
        "evidence_quotes": evidence_quotes,
        "checkpoint_code": (rule_def.get("rule_id") or "AI_RULE")[:64],
        "review_type": review_type,
    }
