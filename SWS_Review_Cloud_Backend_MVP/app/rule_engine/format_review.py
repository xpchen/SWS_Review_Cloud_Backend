"""
格式审查（Format Review）
- 结构完整性（封面要素、目录）
- 编号规范（章节编号、图表编号）
- 引用规范（图表引用）
- 单位与符号规范
- 表格格式

改造为CHECKS字典机制，支持only_checks逐条执行
"""
import re
import logging
from collections import defaultdict
from ..services.checkpoint_runner import ReviewContext
from ..services.block_service import get_block_page_info
from .base import IssueDraft

logger = logging.getLogger(__name__)


# CHECKS字典：check_id -> check函数
CHECKS = {}


def check_cover_required_elements(context: ReviewContext, rule_config: dict) -> list[IssueDraft]:
    """检查封面要素齐全"""
    drafts = []
    
    # 获取前50个blocks
    blocks = sorted(context.blocks_by_id.values(), key=lambda b: b.get("order_index", 0))[:50]
    first_text = " ".join([b.get("text") or "" for b in blocks[:10]])
    
    required_elements = rule_config.get("required_elements", [
        "项目名称", "建设单位", "编制单位", "版本日期"
    ])
    
    missing_elements = [elem for elem in required_elements if elem not in first_text]
    
    if missing_elements:
        first_block_id = blocks[0]["id"] if blocks else None
        if not first_block_id:
            return []
        
        # 获取page_no
        page_info = get_block_page_info([first_block_id])
        page_no = page_info.get(first_block_id, {}).get("page_no", 1)
        
        drafts.append(
            IssueDraft(
                issue_type="FORMAT_STRUCTURE_INCOMPLETE",
                severity="S2",
                title=f"封面要素缺失：{', '.join(missing_elements)}",
                description=f"文档开头未发现以下封面要素：{', '.join(missing_elements)}",
                suggestion="请在文档封面或开头补充上述要素",
                confidence=0.7,
                evidence_block_ids=[first_block_id],
                page_no=page_no,
            )
        )
    
    return drafts


def check_toc_present(context: ReviewContext, rule_config: dict) -> list[IssueDraft]:
    """检查目录存在"""
    drafts = []
    
    blocks = sorted(context.blocks_by_id.values(), key=lambda b: b.get("order_index", 0))[:20]
    has_toc = any("目录" in (b.get("text") or "") for b in blocks)
    
    if not has_toc and context.outline_index:
        first_block_id = blocks[0]["id"] if blocks else None
        if not first_block_id:
            return []
        
        page_info = get_block_page_info([first_block_id])
        page_no = page_info.get(first_block_id, {}).get("page_no", 1)
        
        drafts.append(
            IssueDraft(
                issue_type="FORMAT_MISSING_TOC",
                severity="S3",
                title="缺少目录",
                description="文档中未发现目录页",
                suggestion="建议添加目录页，便于审查和阅读",
                confidence=0.8,
                evidence_block_ids=[first_block_id],
                page_no=page_no,
            )
        )
    
    return drafts


def check_heading_numbering(context: ReviewContext, rule_config: dict) -> list[IssueDraft]:
    """检查章节编号连续性"""
    drafts = []
    
    # 按level分组
    by_level = defaultdict(list)
    for node in context.outline_index.values():
        by_level[node["level"]].append(node)
    
    for level, nodes in by_level.items():
        if level == 1:
            # 一级标题：1, 2, 3...
            expected = 1
            for node in sorted(nodes, key=lambda n: n.get("order_index", 0)):
                node_no = node.get("node_no") or ""
                try:
                    actual = int(node_no.split(".")[0])
                    if actual != expected:
                        heading_block_id = context.outline_heading_block_map.get(node["id"])
                        if not heading_block_id:
                            continue
                        
                        page_info = get_block_page_info([heading_block_id])
                        page_no = page_info.get(heading_block_id, {}).get("page_no", 1)
                        
                        drafts.append(
                            IssueDraft(
                                issue_type="FORMAT_SECTION_NUMBERING",
                                severity="S3",
                                title=f"章节编号不连续：期望{expected}，实际{node_no}",
                                description=f"章节「{node['title']}」编号为{node_no}，与期望编号{expected}不一致",
                                suggestion=f"请将章节编号调整为{expected}，或检查是否有章节缺失",
                                confidence=0.9,
                                evidence_block_ids=[heading_block_id],
                                page_no=page_no,
                            )
                        )
                    expected = actual + 1
                except (ValueError, IndexError):
                    pass
    
    return drafts


def check_table_numbering(context: ReviewContext, rule_config: dict) -> list[IssueDraft]:
    """检查表编号连续且不重复"""
    drafts = []
    
    table_nos = [t.get("table_no") for t in context.tables if t.get("table_no")]
    if len(table_nos) != len(set(table_nos)):
        # 有重复表号
        duplicates = [n for n in set(table_nos) if table_nos.count(n) > 1]
        first_table = context.tables[0] if context.tables else None
        if not first_table:
            return []
        
        # 找到第一个重复表的block_id
        block_id = None
        for block in context.blocks_by_id.values():
            if block.get("table_id") == first_table["id"]:
                block_id = block["id"]
                break
        
        if block_id:
            page_info = get_block_page_info([block_id])
            page_no = page_info.get(block_id, {}).get("page_no", 1)
            
            drafts.append(
                IssueDraft(
                    issue_type="FORMAT_TABLE_NUMBERING_DUPLICATE",
                    severity="S2",
                    title="表号重复",
                    description=f"发现重复的表号：{', '.join(duplicates)}",
                    suggestion="请检查并修正重复的表号",
                    confidence=0.9,
                    evidence_block_ids=[block_id],
                    page_no=page_no,
                )
            )
    
    return drafts


def check_table_caption_present(context: ReviewContext, rule_config: dict) -> list[IssueDraft]:
    """检查表题存在"""
    drafts = []
    
    for table in context.tables:
        table_no = table.get("table_no") or f"表{table['id']}"
        if not table.get("title"):
            # 找到表格对应的block
            block_id = None
            for block in context.blocks_by_id.values():
                if block.get("table_id") == table["id"]:
                    block_id = block["id"]
                    break
            
            if block_id:
                page_info = get_block_page_info([block_id])
                page_no = page_info.get(block_id, {}).get("page_no", 1)
                
                drafts.append(
                    IssueDraft(
                        issue_type="FORMAT_TABLE_MISSING_TITLE",
                        severity="S3",
                        title=f"{table_no}缺少表题",
                        description=f"表格{table_no}未设置表题",
                        suggestion="请为表格添加表题，说明表格内容",
                        confidence=0.9,
                        evidence_block_ids=[block_id],
                        page_no=page_no,
                    )
                )
    
    return drafts


def check_figure_numbering(context: ReviewContext, rule_config: dict) -> list[IssueDraft]:
    """检查图编号连续且不重复（暂未实现，返回空）"""
    # TODO: 需要先实现图件的解析和存储
    return []


def check_figure_caption_present(context: ReviewContext, rule_config: dict) -> list[IssueDraft]:
    """检查图题存在（暂未实现，返回空）"""
    # TODO: 需要先实现图件的解析和存储
    return []


def check_table_referenced(context: ReviewContext, rule_config: dict) -> list[IssueDraft]:
    """检查表格必须被正文引用"""
    drafts = []
    
    # 获取所有文本块
    para_blocks = [b for b in context.blocks_by_id.values() if b.get("block_type") == "PARA"]
    all_text = " ".join([b.get("text") or "" for b in para_blocks])
    
    for table in context.tables:
        table_no = table.get("table_no")
        if not table_no:
            continue
        
        # 查找引用模式
        ref_patterns = [
            rf"见{re.escape(table_no)}",
            rf"如{re.escape(table_no)}",
            rf"{re.escape(table_no)}所示",
            rf"{re.escape(table_no)}可见",
        ]
        
        is_referenced = any(re.search(p, all_text) for p in ref_patterns)
        
        if not is_referenced:
            # 找到表格对应的block
            block_id = None
            for block in context.blocks_by_id.values():
                if block.get("table_id") == table["id"]:
                    block_id = block["id"]
                    break
            
            if block_id:
                page_info = get_block_page_info([block_id])
                page_no = page_info.get(block_id, {}).get("page_no", 1)
                
                drafts.append(
                    IssueDraft(
                        issue_type="FORMAT_TABLE_NOT_REFERENCED",
                        severity="S3",
                        title=f"表格未被引用：{table_no}",
                        description=f"表格{table_no}在正文中未被引用（未出现「见表X」等表述）",
                        suggestion=f"请在正文中添加对{table_no}的引用",
                        confidence=0.8,
                        evidence_block_ids=[block_id],
                        page_no=page_no,
                    )
                )
    
    return drafts


def check_figure_referenced(context: ReviewContext, rule_config: dict) -> list[IssueDraft]:
    """检查图件必须被正文引用（暂未实现，返回空）"""
    # TODO: 需要先实现图件的解析和存储
    return []


def check_unit_symbol_consistency(context: ReviewContext, rule_config: dict) -> list[IssueDraft]:
    """检查单位符号规范：hm²/m³/万元/%写法统一"""
    drafts = []
    
    unit_variants = {
        "hm²": ["hm2", "hm²", "公顷"],
        "m²": ["m2", "m²", "平方米"],
        "m³": ["m3", "m³", "立方米"],
        "万元": ["万元", "万"],
    }
    
    by_table = defaultdict(list)
    for table in context.tables:
        table_no = table.get("table_no") or "未知表"
        for cell in table.get("cells", []):
            by_table[table_no].append(cell)
    
    for table_no, table_cells in by_table.items():
        units_found = set()
        for cell in table_cells:
            unit = cell.get("unit") or ""
            text = cell.get("text") or ""
            for std_unit, variants in unit_variants.items():
                for variant in variants:
                    if variant in unit or variant in text:
                        units_found.add(std_unit)
                        break
        
        if len(units_found) > 1:
            # 找到表格对应的block
            table_id = None
            for table in context.tables:
                if table.get("table_no") == table_no:
                    table_id = table["id"]
                    break
            
            if table_id:
                block_id = None
                for block in context.blocks_by_id.values():
                    if block.get("table_id") == table_id:
                        block_id = block["id"]
                        break
                
                if block_id:
                    page_info = get_block_page_info([block_id])
                    page_no = page_info.get(block_id, {}).get("page_no", 1)
                    
                    drafts.append(
                        IssueDraft(
                            issue_type="FORMAT_UNIT_INCONSISTENT",
                            severity="S2",
                            title=f"{table_no}单位混用",
                            description=f"表格{table_no}中混用了多种单位表示：{', '.join(units_found)}",
                            suggestion="请统一单位表示（如统一使用hm²或m²）",
                            confidence=0.85,
                            evidence_block_ids=[block_id],
                            page_no=page_no,
                        )
                    )
    
    return drafts


def check_typography_normalization(context: ReviewContext, rule_config: dict) -> list[IssueDraft]:
    """检查全角/半角与标点规范（提示级）"""
    # TODO: 实现全角半角检查
    return []


def check_table_unit_column_present(context: ReviewContext, rule_config: dict) -> list[IssueDraft]:
    """检查表格单位列/表头单位缺失"""
    drafts = []
    
    for table in context.tables:
        table_no = table.get("table_no") or f"表{table['id']}"
        
        # 检查表头是否包含"单位"
        header_cells = [c for c in table.get("cells", []) if c.get("r") == 0]
        header_texts = [c.get("text") or "" for c in header_cells]
        has_unit_col = any("单位" in h for h in header_texts)
        
        # 检查是否有数值列
        has_numeric = any(c.get("num_value") is not None for c in table.get("cells", []))
        
        if has_numeric and not has_unit_col:
            # 找到表格对应的block
            block_id = None
            for block in context.blocks_by_id.values():
                if block.get("table_id") == table["id"]:
                    block_id = block["id"]
                    break
            
            if block_id:
                page_info = get_block_page_info([block_id])
                page_no = page_info.get(block_id, {}).get("page_no", 1)
                
                drafts.append(
                    IssueDraft(
                        issue_type="FORMAT_TABLE_MISSING_UNIT_COL",
                        severity="S3",
                        title=f"{table_no}缺少单位列",
                        description=f"表格{table_no}包含数值但表头未注明单位列",
                        suggestion="请在表头添加单位列，或在表题中注明单位",
                        confidence=0.8,
                        evidence_block_ids=[block_id],
                        page_no=page_no,
                    )
                )
    
    return drafts


# 注册所有CHECKS
CHECKS = {
    "cover_required_elements": check_cover_required_elements,
    "toc_present": check_toc_present,
    "heading_numbering": check_heading_numbering,
    "figure_numbering": check_figure_numbering,
    "table_numbering": check_table_numbering,
    "table_caption_present": check_table_caption_present,
    "figure_caption_present": check_figure_caption_present,
    "table_referenced": check_table_referenced,
    "figure_referenced": check_figure_referenced,
    "unit_symbol_consistency": check_unit_symbol_consistency,
    "typography_normalization": check_typography_normalization,
    "table_unit_column_present": check_table_unit_column_present,
}


def run_format_review(context_or_version_id, rule_config: dict) -> list[IssueDraft]:
    """
    格式审查主入口：按only_checks筛选执行
    
    支持两种调用方式：
    1. run_format_review(context: ReviewContext, rule_config) - 新方式
    2. run_format_review(version_id: int, rule_config) - 向后兼容
    """
    from ..services.checkpoint_runner import ReviewContext, build_context
    
    # 检测参数类型：如果是int，则构建context（向后兼容）
    if isinstance(context_or_version_id, int):
        context = build_context(context_or_version_id)
    elif isinstance(context_or_version_id, ReviewContext):
        context = context_or_version_id
    else:
        raise TypeError(f"Expected ReviewContext or int, got {type(context_or_version_id)}")
    """
    格式审查主入口：按only_checks筛选执行
    
    Args:
        context: 审查上下文
        rule_config: 规则配置（包含only_checks列表）
    
    Returns:
        IssueDraft列表
    """
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
            # 继续执行其他check
    
    return drafts
