"""
内容审查（Content Review）
- 章节完备性（必备章节是否存在）
- 条件触发内容（有弃渣→必须有弃渣论证）
- 要素齐备（防治责任范围、预测参数等）

改造为CHECKS字典机制，支持only_checks逐条执行
"""
import re
import logging
from ..services.checkpoint_runner import ReviewContext
from ..services.block_service import get_block_page_info, get_first_block_id
from .base import IssueDraft

logger = logging.getLogger(__name__)

# 必备章节关键词（可配置）
REQUIRED_SECTIONS = {
    "综合说明": ["综合说明", "概述", "总则"],
    "项目概况": ["项目概况", "工程概况"],
    "项目区概况": ["项目区概况", "区域概况"],
    "水土流失预测": ["水土流失预测", "预测"],
    "防治措施": ["防治措施", "水土保持措施"],
    "监测": ["监测", "水土保持监测"],
    "投资": ["投资", "概算", "估算"],
    "管理": ["管理", "组织管理", "实施管理"],
}

# 触发条件→必须项映射
TRIGGER_REQUIREMENTS = {
    "是否弃渣": {
        "keywords": ["弃渣", "弃方", "弃土", "外运"],
        "required_sections": ["弃渣场设置与防护", "弃渣论证", "弃方处理"],
        "required_measures": ["拦挡", "覆盖", "排水"],
    },
    "是否临时用地": {
        "keywords": ["临时用地", "临时占地"],
        "required_sections": ["临时防护", "临时用地恢复"],
    },
    "是否消纳场": {
        "keywords": ["消纳场", "专门存放地"],
        "required_sections": ["禁限区符合性论证", "选址论证"],
    },
}


def check_required_sections(context: ReviewContext, rule_config: dict) -> list[IssueDraft]:
    """检查章节完备性"""
    drafts = []
    
    titles_lower = [o["title"].lower() for o in context.outline_index.values() if o.get("title")]
    all_titles = " ".join(titles_lower)
    
    required = rule_config.get("required_sections", REQUIRED_SECTIONS)
    
    for section_name, keywords in required.items():
        found = any(kw in all_titles for kw in keywords)
        if not found:
            # 使用第一个heading block_id
            first_block_id = None
            if context.outline_index:
                first_outline_id = sorted(context.outline_index.values(), key=lambda n: n.get("order_index", 0))[0]["id"]
                first_block_id = context.outline_heading_block_map.get(first_outline_id)
            
            if not first_block_id:
                blocks = sorted(context.blocks_by_id.values(), key=lambda b: b.get("order_index", 0))
                first_block_id = blocks[0]["id"] if blocks else None
            
            if first_block_id:
                page_info = get_block_page_info([first_block_id])
                page_no = page_info.get(first_block_id, {}).get("page_no", 1)
                
                drafts.append(
                    IssueDraft(
                        issue_type="CONTENT_MISSING_SECTION",
                        severity="S1",
                        title=f"缺少必备章节：{section_name}",
                        description=f"文档大纲中未发现与「{section_name}」相关的章节（关键词：{', '.join(keywords)}）",
                        suggestion=f"请补充「{section_name}」章节，或确认章节标题符合规范要求",
                        confidence=0.8,
                        evidence_block_ids=[first_block_id],
                        page_no=page_no,
                    )
                )
    
    return drafts


def check_trigger_requirements(context: ReviewContext, rule_config: dict) -> list[IssueDraft]:
    """检查条件触发内容：出现某情况→必须有某章节/措施"""
    drafts = []
    
    # 获取所有文本块
    para_blocks = [b for b in context.blocks_by_id.values() if b.get("block_type") == "PARA"]
    all_text = " ".join([b.get("text") or "" for b in para_blocks])
    
    # 获取outline标题
    all_outline_titles = " ".join([o.get("title") or "" for o in context.outline_index.values()])
    
    # 检查触发条件
    triggers = rule_config.get("trigger_requirements", TRIGGER_REQUIREMENTS)
    
    for trigger_key, requirements in triggers.items():
        keywords = requirements.get("keywords", [])
        is_triggered = any(kw in all_text for kw in keywords)
        
        if not is_triggered:
            continue
        
        # 已触发，检查必须项
        required_sections = requirements.get("required_sections", [])
        missing_sections = []
        
        for req_section in required_sections:
            found = any(req_section in (o.get("title") or "") for o in context.outline_index.values())
            if not found:
                missing_sections.append(req_section)
        
        if missing_sections:
            first_block_id = para_blocks[0]["id"] if para_blocks else None
            if first_block_id:
                page_info = get_block_page_info([first_block_id])
                page_no = page_info.get(first_block_id, {}).get("page_no", 1)
                
                drafts.append(
                    IssueDraft(
                        issue_type="CONTENT_TRIGGER_MISSING_REQUIREMENT",
                        severity="S1",
                        title=f"触发条件已满足但缺少必须项：{trigger_key}",
                        description=f"文中存在「{', '.join(keywords)}」相关内容，但缺少以下必须章节：{', '.join(missing_sections)}",
                        suggestion=f"请补充以下章节：{', '.join(missing_sections)}，或补充相关论证内容",
                        confidence=0.85,
                        evidence_block_ids=[first_block_id],
                        page_no=page_no,
                    )
                )
        
        # 检查必须措施组合
        required_measures = requirements.get("required_measures", [])
        if required_measures:
            missing_measures = []
            for measure in required_measures:
                if measure not in all_text and measure not in all_outline_titles:
                    missing_measures.append(measure)
            
            if missing_measures:
                first_block_id = para_blocks[0]["id"] if para_blocks else None
                if first_block_id:
                    page_info = get_block_page_info([first_block_id])
                    page_no = page_info.get(first_block_id, {}).get("page_no", 1)
                    
                    drafts.append(
                        IssueDraft(
                            issue_type="CONTENT_MISSING_MEASURES",
                            severity="S1",
                            title=f"缺少必须措施组合：{trigger_key}",
                            description=f"触发条件「{trigger_key}」已满足，但缺少以下必须措施：{', '.join(missing_measures)}",
                            suggestion=f"请补充以下措施：{', '.join(missing_measures)}",
                            confidence=0.8,
                            evidence_block_ids=[first_block_id],
                            page_no=page_no,
                        )
                    )
    
    return drafts


def check_required_elements(context: ReviewContext, rule_config: dict) -> list[IssueDraft]:
    """检查要素齐备：防治责任范围、预测参数等"""
    drafts = []
    
    para_blocks = [b for b in context.blocks_by_id.values() if b.get("block_type") == "PARA"]
    all_text = " ".join([b.get("text") or "" for b in para_blocks])
    
    # 检查防治责任范围要素
    responsibility_keywords = ["防治责任范围", "责任范围", "防治范围"]
    has_responsibility = any(kw in all_text for kw in responsibility_keywords)
    
    if has_responsibility:
        has_area = any(kw in all_text for kw in ["面积", "hm²", "m²", "公顷"])
        if not has_area:
            first_block_id = para_blocks[0]["id"] if para_blocks else None
            if first_block_id:
                page_info = get_block_page_info([first_block_id])
                page_no = page_info.get(first_block_id, {}).get("page_no", 1)
                
                drafts.append(
                    IssueDraft(
                        issue_type="CONTENT_MISSING_ELEMENT",
                        severity="S2",
                        title="防治责任范围缺少面积信息",
                        description="文中提到防治责任范围，但未明确说明面积数值",
                        suggestion="请在防治责任范围章节补充面积数值及依据",
                        confidence=0.8,
                        evidence_block_ids=[first_block_id],
                        page_no=page_no,
                    )
                )
    
    # 检查水土流失预测要素
    prediction_keywords = ["水土流失预测", "预测"]
    has_prediction = any(kw in all_text for kw in prediction_keywords)
    
    if has_prediction:
        has_partition = any(kw in all_text for kw in ["分区", "预测分区"])
        has_period = any(kw in all_text for kw in ["时段", "施工期", "自然恢复期"])
        has_intensity = any(kw in all_text for kw in ["侵蚀强度", "侵蚀模数"])
        has_amount = any(kw in all_text for kw in ["侵蚀量", "流失量", "t/km²"])
        
        missing = []
        if not has_partition:
            missing.append("分区")
        if not has_period:
            missing.append("时段")
        if not has_intensity:
            missing.append("侵蚀强度/模数")
        if not has_amount:
            missing.append("侵蚀量")
        
        if missing:
            first_block_id = para_blocks[0]["id"] if para_blocks else None
            if first_block_id:
                page_info = get_block_page_info([first_block_id])
                page_no = page_info.get(first_block_id, {}).get("page_no", 1)
                
                drafts.append(
                    IssueDraft(
                        issue_type="CONTENT_MISSING_PREDICTION_ELEMENTS",
                        severity="S2",
                        title="水土流失预测缺少关键要素",
                        description=f"预测章节缺少以下关键要素：{', '.join(missing)}",
                        suggestion=f"请补充以下预测要素：{', '.join(missing)}，并说明参数来源",
                        confidence=0.75,
                        evidence_block_ids=[first_block_id],
                        page_no=page_no,
                    )
                )
    
    return drafts


# CHECKS字典
CHECKS = {
    "required_sections": check_required_sections,
    "trigger_requirements": check_trigger_requirements,
    "required_elements": check_required_elements,
}


def run_content_review(context_or_version_id, rule_config: dict) -> list[IssueDraft]:
    """
    内容审查主入口：按only_checks筛选执行
    
    支持两种调用方式：
    1. run_content_review(context: ReviewContext, rule_config) - 新方式
    2. run_content_review(version_id: int, rule_config) - 向后兼容
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
    
    # 获取only_checks配置
    only_checks = set(rule_config.get("only_checks") or [])
    
    # 如果没有指定only_checks，执行所有check；否则只执行指定的
    to_run = CHECKS.keys() if not only_checks else [k for k in CHECKS.keys() if k in only_checks]
    
    for check_id in to_run:
        try:
            check_fn = CHECKS[check_id]
            check_drafts = check_fn(context, rule_config)
            drafts.extend(check_drafts)
        except Exception as e:
            logger.error(f"Check {check_id} failed: {e}", exc_info=True)
    
    return drafts
