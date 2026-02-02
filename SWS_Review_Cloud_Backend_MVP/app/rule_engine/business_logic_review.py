"""
业务逻辑审查（Business Logic Review）
触发条件→必须项/禁止项检查
"""
from .. import db
from ..settings import settings
from ..services.fact_service import get_facts
from .base import IssueDraft

_schema = settings.DB_SCHEMA

# 禁止性条款（触发→禁止）
PROHIBITION_RULES = {
    "消纳场禁限区": {
        "trigger_keywords": ["消纳场", "专门存放地"],
        "prohibited_keywords": ["水源保护区", "生态红线", "自然保护区核心区"],
        "message": "消纳场不得设置在禁限区内",
    },
}


def run_business_logic_review(context_or_version_id, rule_config: dict) -> list[IssueDraft]:
    """
    业务逻辑审查主入口
    
    支持两种调用方式：
    1. run_business_logic_review(context: ReviewContext, rule_config) - 新方式
    2. run_business_logic_review(version_id: int, rule_config) - 向后兼容
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
    
    # 1. 触发必备论证检查（已在content_review中实现，这里可以补充）
    # 2. 禁止性条款校核
    drafts.extend(_check_prohibition_rules(context, rule_config))
    
    return drafts


def _check_prohibition_rules(context, rule_config: dict) -> list[IssueDraft]:
    """检查禁止性条款"""
    drafts = []
    
    # 从context获取所有文本块
    blocks = [
        b for b in context.blocks_by_id.values()
        if b.get("block_type") in ("PARA", "HEADING") and b.get("text")
    ]
    
    all_text = " ".join([b.get("text") or "" for b in blocks])
    
    # 检查禁止性规则
    prohibitions = rule_config.get("prohibition_rules", PROHIBITION_RULES)
    
    for rule_name, rule_config_item in prohibitions.items():
        trigger_keywords = rule_config_item.get("trigger_keywords", [])
        prohibited_keywords = rule_config_item.get("prohibited_keywords", [])
        
        # 检查是否触发
        is_triggered = any(kw in all_text for kw in trigger_keywords)
        if not is_triggered:
            continue
        
        # 检查是否违反禁止性条款
        violations = []
        for block in blocks:
            text = block.get("text") or ""
            if any(kw in text for kw in trigger_keywords):
                # 在同一段落或附近检查禁止性关键词
                for prohibited_kw in prohibited_keywords:
                    if prohibited_kw in text:
                        violations.append((block["id"], prohibited_kw))
        
        if violations:
            evidence_block_ids = [v[0] for v in violations]
            prohibited_items = list(set([v[1] for v in violations]))
            
            drafts.append(
                IssueDraft(
                    issue_type="BUSINESS_LOGIC_PROHIBITION_VIOLATION",
                    severity="S1",  # 致命级
                    title=f"违反禁止性条款：{rule_name}",
                    description=f"文中存在「{', '.join(trigger_keywords)}」相关内容，但同时出现禁止性区域「{', '.join(prohibited_items)}」",
                    suggestion=rule_config_item.get("message", "请检查并修正，确保符合相关法规要求"),
                    confidence=0.9,
                    evidence_block_ids=evidence_block_ids[:5],
                    page_no=1,
                )
            )
    
    return drafts
