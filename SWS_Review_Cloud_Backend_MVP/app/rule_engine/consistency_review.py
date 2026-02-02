"""
一致性审查（Consistency Review）
基于FactStore的diff算子：同一fact_key在不同位置的值必须一致。
"""
from collections import defaultdict
from .. import db
from ..settings import settings
from ..services.fact_service import get_facts
from .base import IssueDraft

_schema = settings.DB_SCHEMA


def run_consistency_review(context_or_version_id, rule_config: dict) -> list[IssueDraft]:
    """
    一致性审查主入口
    
    支持两种调用方式：
    1. run_consistency_review(context: ReviewContext, rule_config) - 新方式
    2. run_consistency_review(version_id: int, rule_config) - 向后兼容
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
    
    # 从context获取所有事实（已按fact_key分组）
    # 将context.facts字典转换为列表格式
    all_facts = []
    for fact_key, fact_list in context.facts.items():
        all_facts.extend(fact_list)
    
    # 按fact_key分组
    by_key = defaultdict(list)
    for fact in all_facts:
        by_key[fact["fact_key"]].append(fact)
    
    # 对每个fact_key，检查多来源是否一致
    tolerance = rule_config.get("tolerance", 0.01)  # 数值容差
    
    for fact_key, facts in by_key.items():
        if len(facts) < 2:
            continue  # 只有一个来源，无法对比
        
        # 数值型事实对比
        numeric_facts = [f for f in facts if f.get("value_num") is not None]
        if len(numeric_facts) >= 2:
            # 统一单位后对比
            values = []
            for fact in numeric_facts:
                value = fact["value_num"]
                unit = fact.get("unit") or ""
                # 单位换算
                if "万" in unit:
                    value *= 10000
                if unit in ["hm²", "公顷"]:
                    value *= 10000
                values.append((value, fact))
            
            # 检查是否一致
            base_value, base_fact = values[0]
            conflicts = []
            for value, fact in values[1:]:
                diff = abs(value - base_value)
                if diff > tolerance:
                    conflicts.append((fact, value, diff))
            
            if conflicts:
                # 生成冲突报告
                conflict_scopes = [f"{c[0]['scope']}({c[1]})" for c in conflicts]
                base_scope = f"{base_fact['scope']}({base_value})"
                
                evidence_block_ids = [base_fact["source_block_id"]] + [
                    c[0]["source_block_id"] for c in conflicts if c[0].get("source_block_id")
                ]
                evidence_block_ids = [b for b in evidence_block_ids if b]
                
                drafts.append(
                    IssueDraft(
                        issue_type="CONSISTENCY_VALUE_MISMATCH",
                        severity="S1",  # 致命级
                        title=f"{fact_key}不一致",
                        description=f"{fact_key}在不同位置取值不一致：{base_scope} vs {', '.join(conflict_scopes)}",
                        suggestion=f"请统一{fact_key}的取值，建议以出现频次最高或更权威的表格为准",
                        confidence=0.9,
                        evidence_block_ids=evidence_block_ids[:5],  # 最多5个证据块
                        page_no=1,
                    )
                )
        
        # 文本型事实对比
        text_facts = [f for f in facts if f.get("value_text") and not f.get("value_num")]
        if len(text_facts) >= 2:
            texts = set(f.get("value_text") or "" for f in text_facts)
            if len(texts) > 1:
                # 文本不一致
                evidence_block_ids = [f["source_block_id"] for f in text_facts if f.get("source_block_id")]
                scopes = [f["scope"] for f in text_facts]
                
                drafts.append(
                    IssueDraft(
                        issue_type="CONSISTENCY_TEXT_MISMATCH",
                        severity="S1",
                        title=f"{fact_key}文本不一致",
                        description=f"{fact_key}在不同位置表述不一致：{', '.join(scopes)}",
                        suggestion=f"请统一{fact_key}的表述",
                        confidence=0.85,
                        evidence_block_ids=evidence_block_ids[:5],
                        page_no=1,
                    )
                )
    
    return drafts
