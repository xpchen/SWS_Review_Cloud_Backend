from collections import defaultdict
from .. import db
from ..settings import settings
from .base import IssueDraft

_schema = settings.DB_SCHEMA


def run_unit_inconsistent(context_or_version_id, rule_config: dict) -> list[IssueDraft]:
    """
    Check same quantity type (e.g. area) uses inconsistent units (亩 vs 公顷 vs m²).
    
    支持两种调用方式：
    1. run_unit_inconsistent(context: ReviewContext, rule_config) - 新方式
    2. run_unit_inconsistent(version_id: int, rule_config) - 向后兼容
    """
    from ..services.checkpoint_runner import ReviewContext, build_context
    
    # 检测参数类型：如果是int，则构建context（向后兼容）
    if isinstance(context_or_version_id, int):
        context = build_context(context_or_version_id)
    elif isinstance(context_or_version_id, ReviewContext):
        context = context_or_version_id
    else:
        raise TypeError(f"Expected ReviewContext or int, got {type(context_or_version_id)}")
    
    drafts = []
    # 从context的tables中收集所有cells
    cells = []
    for table in context.tables:
        table_id = table["id"]
        table_no = table.get("table_no")
        for cell in table.get("cells", []):
            if cell.get("unit"):
                cell_with_table = dict(cell)
                cell_with_table["table_id"] = table_id
                cell_with_table["table_no"] = table_no
                cells.append(cell_with_table)
    if not cells:
        return drafts
    by_col = defaultdict(list)
    for c in cells:
        by_col[(c["table_id"], c["c"])].append(c)
    units_seen = defaultdict(set)
    for (tid, col), col_cells in by_col.items():
        for c in col_cells:
            units_seen[(tid, col)].add((c.get("unit") or "").strip())
    for (tid, col), units in units_seen.items():
        units = {u for u in units if u}
        if len(units) > 1:
            table_no = next((c.get("table_no") for c in by_col[(tid, col)]), str(tid))
            block_id = _table_block_id(context.version_id, tid)
            drafts.append(
                IssueDraft(
                    issue_type="UNIT_INCONSISTENT",
                    severity="S2",
                    title=f"表{table_no} 同列单位混用",
                    description=f"同一列中出现多种单位: {', '.join(units)}。",
                    suggestion="请统一该列单位（如统一为公顷或亩）。",
                    confidence=0.85,
                    evidence_block_ids=[block_id],
                    page_no=1,
                )
            )
    return drafts


def _table_block_id(version_id: int, table_id: int) -> int:
    row = db.fetch_one(
        f"SELECT id FROM {_schema}.doc_block WHERE version_id = %(v)s AND table_id = %(tid)s LIMIT 1",
        {"v": version_id, "tid": table_id},
    )
    return row["id"] if row else 1
