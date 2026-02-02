"""
表内计算审查（In-table Calculation）
升级版：识别合计行/列、占比计算、单位换算
"""
import re
from collections import defaultdict
from .. import db
from ..settings import settings
from .base import IssueDraft

_schema = settings.DB_SCHEMA

# 合计标识关键词
SUM_KEYWORDS = ["合计", "小计", "总计", "总计", "合计值", "合计金额", "合计面积"]
PERCENTAGE_KEYWORDS = ["占比", "比例", "%", "百分比"]


def run_sum_mismatch(context_or_version_id, rule_config: dict) -> list[IssueDraft]:
    """
    表内计算审查：行合计、列合计、占比计算
    
    支持两种调用方式：
    1. run_sum_mismatch(context: ReviewContext, rule_config) - 新方式
    2. run_sum_mismatch(version_id: int, rule_config) - 向后兼容
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
    tolerance = rule_config.get("tolerance", 0.01)
    rounding = rule_config.get("rounding", 2)  # 小数位数
    
    # 使用context中的tables（已包含cells）
    tables = context.tables
    
    for t in tables:
        # 使用context中已加载的cells
        cells = t.get("cells", [])
        if not cells:
            continue
        
        # 按行组织
        by_row = {}
        for c in cells:
            r = c["r"]
            by_row.setdefault(r, []).append(c)
        
        # 按列组织
        by_col = {}
        for c in cells:
            col_idx = c["c"]
            by_col.setdefault(col_idx, []).append(c)
        
        # 1. 检查行合计（合计行 = 该行各列之和）
        drafts.extend(_check_row_sums(context.version_id, t, by_row, tolerance, rounding))
        
        # 2. 检查列合计（合计列 = 该列各行之和）
        drafts.extend(_check_col_sums(context.version_id, t, by_row, by_col, tolerance, rounding))
        
        # 3. 检查占比计算
        drafts.extend(_check_percentages(context.version_id, t, by_row, by_col, tolerance))
    
    return drafts


def _check_row_sums(version_id: int, table: dict, by_row: dict, tolerance: float, rounding: int) -> list[IssueDraft]:
    """检查行合计"""
    drafts = []
    table_no = table.get("table_no") or f"表{table['id']}"
    
    for r_idx, row_cells in by_row.items():
        # 识别合计行
        row_text = " ".join([c.get("text") or "" for c in row_cells])
        is_sum_row = any(kw in row_text for kw in SUM_KEYWORDS)
        
        if not is_sum_row:
            continue
        
        # 找到数值列
        numeric_cols = {}
        for cell in row_cells:
            col_idx = cell["c"]
            num_value = cell.get("num_value")
            if num_value is not None:
                numeric_cols[col_idx] = num_value
        
        # 对每个数值列，检查是否等于该列上面行的和
        for col_idx, sum_value in numeric_cols.items():
            # 获取该列的所有值（不包括合计行本身）
            col_values = []
            for r, cells in by_row.items():
                if r == r_idx:
                    continue
                for cell in cells:
                    if cell["c"] == col_idx:
                        num_val = cell.get("num_value")
                        if num_val is not None:
                            col_values.append(num_val)
            
            if len(col_values) < 2:
                continue
            
            computed_sum = sum(col_values)
            diff = abs(sum_value - computed_sum)
            
            if diff > tolerance:
                # 生成计算轨迹
                calc_trace = " + ".join([str(round(v, rounding)) for v in col_values])
                calc_trace += f" = {round(computed_sum, rounding)} ≠ {round(sum_value, rounding)}"
                
                block_id = _table_block_id(version_id, table["id"])
                drafts.append(
                    IssueDraft(
                        issue_type="SUM_MISMATCH_ROW",
                        severity="S1",  # 致命级
                        title=f"{table_no} 行合计错误（第{r_idx+1}行）",
                        description=f"合计行第{col_idx+1}列的值{sum_value}与分项之和{computed_sum}不一致。计算过程：{calc_trace}",
                        suggestion="请核对分项值来源，重新计算合计。如涉及取整，请统一取整规则。",
                        confidence=0.95,
                        evidence_block_ids=[block_id],
                        page_no=1,
                    )
                )
    
    return drafts


def _check_col_sums(version_id: int, table: dict, by_row: dict, by_col: dict, tolerance: float, rounding: int) -> list[IssueDraft]:
    """检查列合计"""
    drafts = []
    table_no = table.get("table_no") or f"表{table['id']}"
    
    for col_idx, col_cells in by_col.items():
        # 识别合计列（检查列头或最后一行的该列）
        col_header = None
        for cell in col_cells:
            if cell["r"] == 0:  # 假设第一行是表头
                col_header = cell.get("text") or ""
                break
        
        is_sum_col = col_header and any(kw in col_header for kw in SUM_KEYWORDS)
        
        if not is_sum_col:
            continue
        
        # 获取该列的所有数值（不包括表头）
        col_values = []
        for cell in col_cells:
            if cell["r"] == 0:
                continue
            num_val = cell.get("num_value")
            if num_val is not None:
                col_values.append(num_val)
        
        if len(col_values) < 2:
            continue
        
        # 最后一个是合计值
        sum_value = col_values[-1]
        computed_sum = sum(col_values[:-1])
        diff = abs(sum_value - computed_sum)
        
        if diff > tolerance:
            calc_trace = " + ".join([str(round(v, rounding)) for v in col_values[:-1]])
            calc_trace += f" = {round(computed_sum, rounding)} ≠ {round(sum_value, rounding)}"
            
            block_id = _table_block_id(version_id, table["id"])
            drafts.append(
                IssueDraft(
                    issue_type="SUM_MISMATCH_COL",
                    severity="S1",
                    title=f"{table_no} 列合计错误（第{col_idx+1}列）",
                    description=f"合计列的值{sum_value}与分项之和{computed_sum}不一致。计算过程：{calc_trace}",
                    suggestion="请核对分项值，重新计算合计。",
                    confidence=0.95,
                    evidence_block_ids=[block_id],
                    page_no=1,
                )
            )
    
    return drafts


def _check_percentages(version_id: int, table: dict, by_row: dict, by_col: dict, tolerance: float) -> list[IssueDraft]:
    """检查占比计算：占比列 = 明细/总计，占比列合计 = 100%"""
    drafts = []
    table_no = table.get("table_no") or f"表{table['id']}"
    
    # 查找占比列
    header_row = by_row.get(0, [])
    percentage_cols = []
    for cell in header_row:
        text = cell.get("text") or ""
        if any(kw in text for kw in PERCENTAGE_KEYWORDS):
            percentage_cols.append(cell["c"])
    
    for col_idx in percentage_cols:
        col_cells = by_col.get(col_idx, [])
        percentages = []
        total_value = None
        
        # 获取该列的百分比值
        for cell in col_cells:
            if cell["r"] == 0:
                continue
            num_val = cell.get("num_value")
            text = cell.get("text") or ""
            # 提取百分比（可能是数值或带%的文本）
            if num_val is not None:
                # 如果是百分比格式（0-1之间），转换为百分比
                if 0 <= num_val <= 1:
                    percentages.append(num_val * 100)
                elif num_val <= 100:
                    percentages.append(num_val)
            elif "%" in text:
                # 从文本提取百分比
                match = re.search(r"([\d.]+)%", text)
                if match:
                    percentages.append(float(match.group(1)))
        
        # 检查占比列合计是否为100%
        if len(percentages) >= 2:
            sum_percent = sum(percentages)
            if abs(sum_percent - 100) > tolerance:
                block_id = _table_block_id(version_id, table["id"])
                drafts.append(
                    IssueDraft(
                        issue_type="PERCENTAGE_SUM_MISMATCH",
                        severity="S2",
                        title=f"{table_no} 占比列合计不为100%",
                        description=f"占比列（第{col_idx+1}列）各项占比之和为{sum_percent}%，不等于100%",
                        suggestion="请核对各项占比值，确保合计为100%",
                        confidence=0.9,
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
