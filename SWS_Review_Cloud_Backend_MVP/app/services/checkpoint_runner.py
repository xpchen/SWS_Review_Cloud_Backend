"""
Checkpoint Runner：统一的执行上下文和checkpoint调度
- 一次构建context，300+checkpoint复用
- 避免重复查询数据库
- 支持only_checks机制
"""
import logging
from dataclasses import dataclass
from typing import Callable
from .. import db
from ..settings import settings
from ..rule_engine.base import IssueDraft
from .fact_service import get_facts

_schema = settings.DB_SCHEMA
logger = logging.getLogger(__name__)


@dataclass
class ReviewContext:
    """审查执行上下文：一次性构建，供所有checkpoint复用"""
    version_id: int
    outline_index: dict[int, dict]  # {outline_node_id: {node_no, title, level, parent_id, order_index}}
    blocks_by_id: dict[int, dict]  # {block_id: block_data}
    blocks_by_outline: dict[int, list[dict]]  # {outline_node_id: [blocks]}
    tables: list[dict]  # 结构化表格数据（包含cells）
    facts: dict  # fact_service输出：{fact_key: [{value_num, value_text, unit, scope, ...}]}
    outline_heading_block_map: dict[int, int]  # {outline_node_id: heading_block_id}


def build_context(version_id: int) -> ReviewContext:
    """
    构建审查执行上下文
    
    Args:
        version_id: 文档版本ID
    
    Returns:
        ReviewContext对象，包含所有需要的数据结构
    """
    # 1. 加载outline节点
    outline_nodes = db.fetch_all(
        f"""
        SELECT id, node_no, title, level, parent_id, order_index
        FROM {_schema}.doc_outline_node
        WHERE version_id = %(v)s
        ORDER BY order_index
        """,
        {"v": version_id}
    )
    outline_index = {n["id"]: n for n in outline_nodes}
    
    # 2. 加载所有blocks
    blocks = db.fetch_all(
        f"""
        SELECT id, outline_node_id, block_type, order_index, text, table_id
        FROM {_schema}.doc_block
        WHERE version_id = %(v)s
        ORDER BY order_index
        """,
        {"v": version_id}
    )
    blocks_by_id = {b["id"]: b for b in blocks}
    
    # 按outline_node_id分组blocks
    blocks_by_outline: dict[int, list[dict]] = {}
    for block in blocks:
        outline_id = block.get("outline_node_id")
        if outline_id:
            if outline_id not in blocks_by_outline:
                blocks_by_outline[outline_id] = []
            blocks_by_outline[outline_id].append(block)
    
    # 3. 加载表格（包含cells）
    tables_raw = db.fetch_all(
        f"""
        SELECT id, version_id, outline_node_id, table_no, title, n_rows, n_cols, raw_json
        FROM {_schema}.doc_table
        WHERE version_id = %(v)s
        ORDER BY id
        """,
        {"v": version_id}
    )
    
    # 为每个表格加载cells
    tables = []
    for table in tables_raw:
        table_id = table["id"]
        cells = db.fetch_all(
            f"""
            SELECT id, r, c, text, num_value, unit
            FROM {_schema}.doc_table_cell
            WHERE table_id = %(tid)s
            ORDER BY r, c
            """,
            {"tid": table_id}
        )
        table["cells"] = cells
        tables.append(table)
    
    # 4. 加载facts
    facts_raw = get_facts(version_id)
    # 按fact_key分组
    facts: dict[str, list[dict]] = {}
    for fact in facts_raw:
        fact_key = fact.get("fact_key")
        if fact_key:
            if fact_key not in facts:
                facts[fact_key] = []
            facts[fact_key].append(fact)
    
    # 5. 加载outline到heading block的映射
    outline_heading_block_map = {}
    for outline_id in outline_index.keys():
        heading_block = db.fetch_one(
            f"""
            SELECT id FROM {_schema}.doc_block
            WHERE version_id = %(v)s
            AND outline_node_id = %(oid)s
            AND block_type = 'HEADING'
            LIMIT 1
            """,
            {"v": version_id, "oid": outline_id}
        )
        if heading_block:
            outline_heading_block_map[outline_id] = heading_block["id"]
    
    return ReviewContext(
        version_id=version_id,
        outline_index=outline_index,
        blocks_by_id=blocks_by_id,
        blocks_by_outline=blocks_by_outline,
        tables=tables,
        facts=facts,
        outline_heading_block_map=outline_heading_block_map,
    )


def run_checkpoints(
    context: ReviewContext,
    engine_type: str,
    executor_registry: dict[str, Callable],
) -> list[tuple[IssueDraft, str]]:
    """
    执行指定engine_type的所有checkpoint
    
    Args:
        context: 审查上下文
        engine_type: 引擎类型（'RULE'/'AI'/'SQL'）
        executor_registry: executor注册表
    
    Returns:
        [(IssueDraft, checkpoint_code)] 列表
    """
    drafts_with_checkpoint = []
    
    # 查询启用的checkpoint
    # 检查字段是否存在，向后兼容旧schema
    try:
        # 尝试查询包含新字段的完整查询
        checkpoints = db.fetch_all(
            f"""
            SELECT id, code, name, review_category, engine_type, rule_config_json, enabled
            FROM {_schema}.review_checkpoint
            WHERE enabled = true
            AND (engine_type = %(et)s OR (engine_type IS NULL AND %(et)s = 'RULE'))
            ORDER BY order_index NULLS LAST, id
            """,
            {"et": engine_type}
        )
    except Exception as e:
        # 如果字段不存在，使用兼容旧schema的查询
        error_str = str(e)
        if "review_category" in error_str or "engine_type" in error_str:
            logger.warning("新字段不存在，使用兼容旧schema的查询。请执行迁移006_checkpoint_schema_refactor.sql")
            # 根据engine_type参数，使用category字段过滤
            if engine_type == "RULE":
                # RULE类型：排除AI类型的checkpoint
                checkpoints = db.fetch_all(
                    f"""
                    SELECT id, code, name, category as review_category, 
                           'RULE' as engine_type,
                           rule_config_json, enabled
                    FROM {_schema}.review_checkpoint
                    WHERE enabled = true
                    AND (category IS NULL OR category != 'AI')
                    ORDER BY order_index NULLS LAST, id
                    """,
                    {}
                )
            elif engine_type == "AI":
                # AI类型：只查询AI类型的checkpoint
                checkpoints = db.fetch_all(
                    f"""
                    SELECT id, code, name, category as review_category, 
                           'AI' as engine_type,
                           rule_config_json, enabled
                    FROM {_schema}.review_checkpoint
                    WHERE enabled = true
                    AND category = 'AI'
                    ORDER BY order_index NULLS LAST, id
                    """,
                    {}
                )
            else:
                # 其他类型：返回空列表
                checkpoints = []
        else:
            raise
    
    if not checkpoints:
        logger.warning(f"No {engine_type} checkpoints found for version {context.version_id}")
        return drafts_with_checkpoint
    
    # 循环执行checkpoint
    for checkpoint in checkpoints:
        checkpoint_code = checkpoint["code"]
        rule_config = checkpoint.get("rule_config_json") or {}
        executor_name = rule_config.get("executor") or checkpoint_code.lower()
        
        executor_fn = executor_registry.get(executor_name)
        if not executor_fn:
            logger.warning(f"Unknown executor '{executor_name}' for checkpoint {checkpoint_code}, skipping")
            continue
        
        try:
            # 调用executor，传入context而非version_id
            drafts = executor_fn(context, rule_config)
            for draft in drafts:
                drafts_with_checkpoint.append((draft, checkpoint_code))
            logger.info(f"Checkpoint {checkpoint_code} ({executor_name}) produced {len(drafts)} issues")
        except Exception as e:
            logger.error(
                f"Error running checkpoint {checkpoint_code} (executor: {executor_name}): {e}",
                exc_info=True
            )
            # 不中断，继续执行其他checkpoint
    
    return drafts_with_checkpoint
