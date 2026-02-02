from .. import db
from ..settings import settings
from .base import IssueDraft

_schema = settings.DB_SCHEMA


def run_key_field_inconsistent(context_or_version_id, rule_config: dict) -> list[IssueDraft]:
    """
    Check key fields (e.g. project name, area) are consistent across document.
    
    支持两种调用方式：
    1. run_key_field_inconsistent(context: ReviewContext, rule_config) - 新方式
    2. run_key_field_inconsistent(version_id: int, rule_config) - 向后兼容
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
    # 从context获取所有段落块
    blocks = [
        b for b in context.blocks_by_id.values()
        if b.get("block_type") == "PARA" and b.get("text")
    ]
    blocks.sort(key=lambda x: x.get("order_index", 0))
    if len(blocks) < 2:
        return drafts
    # MVP: simple heuristic - if "占地面积" or "面积" appears with different numbers in different blocks, flag
    import re
    area_mentions = []
    for b in blocks:
        m = re.search(r"占地面积?\s*[：:]\s*([\d.]+)\s*([万]?)\s*(公顷|亩|m²|平方米)", (b.get("text") or ""))
        if m:
            area_mentions.append((b["id"], m.group(1), m.group(3)))
    if len(area_mentions) >= 2:
        vals = set((v[1], v[2]) for v in area_mentions)
        if len(vals) > 1:
            drafts.append(
                IssueDraft(
                    issue_type="KEY_FIELD_INCONSISTENT",
                    severity="S2",
                    title="关键字段（占地面积）表述不一致",
                    description="文档中多处提及占地面积，数值或单位不一致。",
                    suggestion="请统一占地面积数据及单位，确保全文一致。",
                    confidence=0.75,
                    evidence_block_ids=[area_mentions[0][0], area_mentions[1][0]],
                    page_no=1,
                )
            )
    return drafts
