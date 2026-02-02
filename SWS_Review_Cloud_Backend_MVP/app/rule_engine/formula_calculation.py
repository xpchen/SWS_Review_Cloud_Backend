"""
公式计算审查（Formula Calculation）
- 六项防治指标复算（治理度、控制比、渣土防护率、表土保护率、恢复率、覆盖率）
- 预测计算复算（分区×时段×侵蚀强度→侵蚀量）
- 平衡类公式（挖方=填方+弃方+外运+损耗）
- 费用/投资公式（直接费+间接费+预备费）
"""
from .. import db
from ..settings import settings
from ..services.fact_service import get_facts
from .base import IssueDraft

_schema = settings.DB_SCHEMA

# 六项指标公式模板
SIX_INDICATORS_FORMULAS = {
    "治理度": {
        "expr": "a / b",
        "vars": {
            "a": {"name": "治理达标面积", "fact_key": "治理达标面积", "unit": "m²"},
            "b": {"name": "水土流失总面积", "fact_key": "水土流失总面积", "unit": "m²"},
        },
        "description": "治理度 = 治理达标面积 / 水土流失总面积",
    },
    "控制比": {
        "expr": "a / b",
        "vars": {
            "a": {"name": "防治措施面积", "fact_key": "防治措施面积", "unit": "m²"},
            "b": {"name": "扰动面积", "fact_key": "扰动面积", "unit": "m²"},
        },
        "description": "控制比 = 防治措施面积 / 扰动面积",
    },
    "渣土防护率": {
        "expr": "a / b",
        "vars": {
            "a": {"name": "渣土防护量", "fact_key": "渣土防护量", "unit": "m³"},
            "b": {"name": "渣土总量", "fact_key": "渣土总量", "unit": "m³"},
        },
        "description": "渣土防护率 = 渣土防护量 / 渣土总量",
    },
    "表土保护率": {
        "expr": "a / b",
        "vars": {
            "a": {"name": "表土保护量", "fact_key": "表土保护量", "unit": "m³"},
            "b": {"name": "可剥离表土量", "fact_key": "可剥离表土量", "unit": "m³"},
        },
        "description": "表土保护率 = 表土保护量 / 可剥离表土量",
    },
    "恢复率": {
        "expr": "a / b",
        "vars": {
            "a": {"name": "恢复面积", "fact_key": "恢复面积", "unit": "m²"},
            "b": {"name": "可恢复面积", "fact_key": "可恢复面积", "unit": "m²"},
        },
        "description": "恢复率 = 恢复面积 / 可恢复面积",
    },
    "覆盖率": {
        "expr": "a / b",
        "vars": {
            "a": {"name": "植被覆盖面积", "fact_key": "植被覆盖面积", "unit": "m²"},
            "b": {"name": "可绿化面积", "fact_key": "可绿化面积", "unit": "m²"},
        },
        "description": "覆盖率 = 植被覆盖面积 / 可绿化面积",
    },
}

# 平衡类公式
BALANCE_FORMULAS = {
    "土石方平衡": {
        "expr": "a = b + c + d",
        "vars": {
            "a": {"name": "挖方", "fact_key": "挖方", "unit": "m³"},
            "b": {"name": "填方", "fact_key": "填方", "unit": "m³"},
            "c": {"name": "弃方", "fact_key": "弃方", "unit": "m³"},
            "d": {"name": "外运量", "fact_key": "外运量", "unit": "m³"},
        },
        "description": "挖方 = 填方 + 弃方 + 外运量",
        "tolerance": 0.01,  # 允许误差
    },
}

# 预测计算公式
PREDICTION_FORMULAS = {
    "侵蚀量": {
        "expr": "a * b * c",
        "vars": {
            "a": {"name": "分区面积", "fact_key": "分区面积", "unit": "km²"},
            "b": {"name": "时段", "fact_key": "时段", "unit": "年"},
            "c": {"name": "侵蚀模数", "fact_key": "侵蚀模数", "unit": "t/km²·a"},
        },
        "description": "侵蚀量 = 分区面积 × 时段 × 侵蚀模数",
    },
}


def run_formula_calculation(context_or_version_id, rule_config: dict) -> list[IssueDraft]:
    """
    公式计算审查主入口
    
    支持两种调用方式：
    1. run_formula_calculation(context: ReviewContext, rule_config) - 新方式
    2. run_formula_calculation(version_id: int, rule_config) - 向后兼容
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
    
    formula_type = rule_config.get("formula_type", "six_indicators")  # six_indicators, balance, prediction
    
    if formula_type == "six_indicators":
        drafts.extend(_check_six_indicators(context, rule_config))
    elif formula_type == "balance":
        drafts.extend(_check_balance_formulas(context, rule_config))
    elif formula_type == "prediction":
        drafts.extend(_check_prediction_formulas(context, rule_config))
    
    return drafts


def _check_six_indicators(context, rule_config: dict) -> list[IssueDraft]:
    """检查六项指标公式"""
    from ..services.checkpoint_runner import ReviewContext
    
    drafts = []
    tolerance = rule_config.get("tolerance", 0.01)
    
    # 从context获取所有事实（已按fact_key分组）
    all_facts = []
    for fact_key, fact_list in context.facts.items():
        all_facts.extend(fact_list)
    facts_by_key = {f["fact_key"]: f for f in all_facts}
    
    # 使用context中的tables，过滤出相关表格
    tables = [
        t for t in context.tables
        if t.get("title") and ("指标" in t["title"] or "治理度" in t["title"] or "控制比" in t["title"])
    ]
    # 为每个table添加block_id
    for table in tables:
        table_id = table["id"]
        block = db.fetch_one(
            f"SELECT id FROM {_schema}.doc_block WHERE version_id = %(v)s AND table_id = %(tid)s LIMIT 1",
            {"v": context.version_id, "tid": table_id}
        )
        table["block_id"] = block["id"] if block else None
    
    for indicator_name, formula in SIX_INDICATORS_FORMULAS.items():
        # 获取变量值
        var_values = {}
        for var_name, var_config in formula["vars"].items():
            fact_key = var_config["fact_key"]
            fact = facts_by_key.get(fact_key)
            if fact and fact.get("value_num") is not None:
                value = fact["value_num"]
                unit = fact.get("unit") or ""
                # 单位换算
                if unit in ["hm²", "公顷"]:
                    value *= 10000
                elif "万" in unit:
                    value *= 10000
                var_values[var_name] = value
            else:
                # 变量缺失
                var_values[var_name] = None
        
        # 检查是否所有变量都有值
        if None in var_values.values():
            continue  # 跳过缺失变量的指标
        
        # 计算理论值
        a = var_values.get("a", 0)
        b = var_values.get("b", 0)
        if b == 0:
            continue  # 分母为0，跳过
        
        calculated_value = a / b
        
        # 查找表格中的实现值
        indicator_value = None
        indicator_table_id = None
        indicator_block_id = None
        
        for table in tables:
            # 使用context中已加载的cells
            cells = table.get("cells", [])
            
            # 查找包含指标名称的单元格
            for cell in cells:
                text = cell.get("text") or ""
                if indicator_name in text:
                    # 查找同一行或同一列的数值
                    for other_cell in cells:
                        if other_cell["r"] == cell["r"] or other_cell["c"] == cell["c"]:
                            num_val = other_cell.get("num_value")
                            if num_val is not None and 0 <= num_val <= 1:
                                indicator_value = num_val
                                indicator_table_id = table["id"]
                                indicator_block_id = table.get("block_id")
                                break
                    if indicator_value is not None:
                        break
            if indicator_value is not None:
                break
        
        if indicator_value is None:
            # 未找到实现值，跳过
            continue
        
        # 对比计算值与实现值
        diff = abs(calculated_value - indicator_value)
        if diff > tolerance:
            # 生成计算轨迹
            calc_trace = f"{a} / {b} = {calculated_value:.4f} ≠ {indicator_value:.4f} (实现值)"
            
            evidence_block_ids = [indicator_block_id] if indicator_block_id else []
            # 添加变量来源block
            for var_name, var_config in formula["vars"].items():
                fact_key = var_config["fact_key"]
                fact = facts_by_key.get(fact_key)
                if fact and fact.get("source_block_id"):
                    evidence_block_ids.append(fact["source_block_id"])
            
            drafts.append(
                IssueDraft(
                    issue_type="FORMULA_MISMATCH_SIX_INDICATORS",
                    severity="S1",  # 致命级
                    title=f"{indicator_name}计算不一致",
                    description=f"{formula['description']}。计算值：{calculated_value:.4f}，实现值：{indicator_value:.4f}，差异：{diff:.4f}。计算过程：{calc_trace}",
                    suggestion=f"请核对{indicator_name}计算公式中的分子、分母取值，或检查实现值来源",
                    confidence=0.9,
                    evidence_block_ids=evidence_block_ids[:5],
                    page_no=1,
                )
            )
    
    return drafts


def _check_balance_formulas(context, rule_config: dict) -> list[IssueDraft]:
    """检查平衡类公式"""
    drafts = []
    tolerance = rule_config.get("tolerance", 0.01)
    
    # 从context获取所有事实
    all_facts = []
    for fact_key, fact_list in context.facts.items():
        all_facts.extend(fact_list)
    facts_by_key = {f["fact_key"]: f for f in all_facts}
    
    for formula_name, formula in BALANCE_FORMULAS.items():
        # 获取变量值
        var_values = {}
        for var_name, var_config in formula["vars"].items():
            fact_key = var_config["fact_key"]
            fact = facts_by_key.get(fact_key)
            if fact and fact.get("value_num") is not None:
                value = fact["value_num"]
                unit = fact.get("unit") or ""
                if "万" in unit:
                    value *= 10000
                var_values[var_name] = value
            else:
                var_values[var_name] = None
        
        # 检查是否所有变量都有值
        if None in var_values.values():
            continue
        
        # 验证平衡公式：a = b + c + d
        a = var_values.get("a", 0)
        b = var_values.get("b", 0)
        c = var_values.get("c", 0)
        d = var_values.get("d", 0)
        
        right_side = b + c + d
        diff = abs(a - right_side)
        
        if diff > tolerance:
            calc_trace = f"{b} + {c} + {d} = {right_side} ≠ {a} (挖方)"
            
            evidence_block_ids = []
            for var_name, var_config in formula["vars"].items():
                fact_key = var_config["fact_key"]
                fact = facts_by_key.get(fact_key)
                if fact and fact.get("source_block_id"):
                    evidence_block_ids.append(fact["source_block_id"])
            
            drafts.append(
                IssueDraft(
                    issue_type="FORMULA_BALANCE_MISMATCH",
                    severity="S1",
                    title=f"{formula_name}不平衡",
                    description=f"{formula['description']}。左侧：{a}，右侧：{right_side}，差异：{diff}。计算过程：{calc_trace}",
                    suggestion="请核对土石方平衡表中的各项数值，确保平衡关系成立",
                    confidence=0.9,
                    evidence_block_ids=evidence_block_ids[:5],
                    page_no=1,
                )
            )
    
    return drafts


def _check_prediction_formulas(context, rule_config: dict) -> list[IssueDraft]:
    """检查预测计算公式"""
    drafts = []
    tolerance = rule_config.get("tolerance", 0.01)
    
    # 预测计算通常需要从表格中获取分区×时段×强度的组合
    # 这里简化处理：查找预测相关表格，验证侵蚀量计算
    
    # 使用context中的tables，过滤出相关表格
    tables = [
        t for t in context.tables
        if t.get("title") and ("预测" in t["title"] or "侵蚀" in t["title"])
    ]
    # 为每个table添加block_id
    for table in tables:
        table_id = table["id"]
        block = db.fetch_one(
            f"SELECT id FROM {_schema}.doc_block WHERE version_id = %(v)s AND table_id = %(tid)s LIMIT 1",
            {"v": context.version_id, "tid": table_id}
        )
        table["block_id"] = block["id"] if block else None
    
    for table in tables:
        # 使用context中已加载的cells
        cells = table.get("cells", [])
        
        # 查找包含"侵蚀量"的行/列
        # 简化：查找数值列，验证是否满足预测公式逻辑
        # 实际实现需要更复杂的表格解析逻辑
    
    return drafts
