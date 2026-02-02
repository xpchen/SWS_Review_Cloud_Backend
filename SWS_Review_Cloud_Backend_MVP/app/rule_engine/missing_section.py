from .. import db
from ..settings import settings
from ..services.block_service import get_heading_block_id, get_first_block_id
from .base import IssueDraft

_schema = settings.DB_SCHEMA

REQUIRED_SECTIONS = [
    "综合说明",
    "项目概况",
    "项目区概况",
    "水土保持",
    "投资",
    "结论",
]


def run_missing_section(context_or_version_id, rule_config: dict) -> list[IssueDraft]:
    """
    Check required outline sections exist (by title keyword).
    
    支持两种调用方式：
    1. run_missing_section(context: ReviewContext, rule_config) - 新方式
    2. run_missing_section(version_id: int, rule_config) - 向后兼容
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
    # 从context获取outline
    outline = list(context.outline_index.values())
    outline.sort(key=lambda x: x.get("order_index", 0))
    titles_lower = [(o["title"] or "").strip().lower() for o in outline]
    for req in REQUIRED_SECTIONS:
        if not any(req in t for t in titles_lower):
            # 使用heading block_id，而不是outline_node.id
            first_block_id = get_first_block_id(context.version_id)
            if outline:
                first_outline_id = outline[0]["id"]
                heading_block_id = get_heading_block_id(context.version_id, first_outline_id)
                if heading_block_id:
                    first_block_id = heading_block_id
            
            drafts.append(
                IssueDraft(
                    issue_type="MISSING_SECTION",
                    severity="S1",
                    title=f"缺少必备章节：{req}",
                    description=f"文档大纲中未发现与「{req}」相关的章节，可能影响审查完整性。",
                    suggestion="请补充相应章节或确认章节标题符合规范要求。",
                    confidence=0.8,
                    evidence_block_ids=[first_block_id],
                    page_no=1,
                )
            )
    return drafts
