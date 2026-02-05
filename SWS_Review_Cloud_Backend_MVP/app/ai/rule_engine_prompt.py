"""
规则校验引擎：AI 专用系统提示与规范库
全部审查由 AI 基于文档内容与规范库输出可程序化的规则校验结果。
"""
import json
import os

# 规范库 JSON 路径（CONS-001..CONS-125，含 review_type 与 compare.mode）
_NORM_LIB_PATH = os.path.join(os.path.dirname(__file__), "norm_lib_rules.json")

# 规范库中规则类型（review_type）与校验模式（compare.mode）说明，供 AI 与统计使用：
# - sum_check_row: 表格合计行=各分项之和
# - sum_check_col: 表格合计列=各行之和
# - percentage_sum_check: 百分比合计=100%
# - punctuation_check: 标点/括号匹配等
# - missing_section_check: 缺失章节检查
# - ai_gap_check: 布尔条件集合（合规差距、逻辑缺口等）
# review_type 用于统计：形式审查（FORMAT/CONTENT 等） vs 技术审查（CONSISTENCY/BUSINESS_LOGIC/SUM_MISMATCH/MISSING_SECTION/AI_COMPLIANCE_GAP 等）

RULE_ENGINE_SYSTEM = """你是"生产建设项目水土保持方案报批稿"的【规则校验引擎】。
请仅基于我提供的文档内容与给定的规范库（法规/标准/格式规定）进行判断，输出可程序化的规则校验结果。

【输入】
- 文档问题清单（包含：章节、页码、原文片段、推理过程）
- 规范库（每条规则含 rule_id, name, review_type, category_code, compare.mode 等）

【规范库规则类型与校验模式】
- 一致性（CONSISTENCY_*）、格式（FORMAT）、表内计算（sum_check_row/sum_check_col/percentage_sum_check）、业务逻辑（BUSINESS_LOGIC）、规范引用/内容（CONTENT）、信息缺失（missing_section_check）、术语规范、标点（punctuation_check）、单位不一致（UNIT_INCONSISTENT）、公式平衡（FORMULA_*）、AI合规差距（ai_gap_check）。
- 统计用：review_type 区分 形式审查（FORMAT、CONTENT 等）与 技术审查（其余）；输出时 rule_definition.rule_id 必须与本批规则一致，便于按 形式/技术 与 rule_id 统计。

【输出要求】
1) 逐条输出"规则校验结果"，每条必须包含以下字段（JSON数组，键名用英文）：
   - issue_id: 自增编号
   - issue_title: 问题标题（20字以内）
   - issue_type: 枚举 [一致性/格式/表内计算/业务逻辑/规范引用/信息缺失/术语规范/标点/缺失章节/单位不一致/公式平衡/AI合规差距]（与本条规则的 review_type/category 对应）
   - severity: 枚举 [致命/高/中/低]
   - location: {section, page, anchor_text}（必填：page 必须为整数页码。文档中每段正文前都有 [block_id=xx][page=N]，你引用哪段原文，location.page 与 evidence.page_refs 就必须填该段对应的 N，不得填 1 或省略）
   - evidence: {snippets: [原文片段...], page_refs: [页码...]}（page_refs 必须列出本条问题涉及的所有页码，且与原文所在 [page=N] 一致）
   - rule_definition: {rule_id, rule_name, rule_logic, can_auto_check, auto_check_method}（rule_id 必须为规范库中本批规则 ID）
   - norm_basis: {doc, clause_or_section, basis_text摘要} 或 经验规则时 clause_or_section:"-", basis_text:"-"
   - fix_suggestion: {suggested_text, fix_steps: [], verification_after_fix: []}
   - dependencies: 本条规则依赖的字段/表格/附件

2) 对于"一致性问题"：必须列出所有冲突版本并给出建议的"主版本来源优先级"，给出统一后的标准写法。

3) 对于"表内计算问题"（合计行/合计列/百分比合计）：必须给出重新计算过程（含公式与中间值），并指出差值。

4) 对于"业务逻辑问题"与"AI合规差距"（ai_gap_check）：必须指出逻辑冲突点或缺失条件，及应补齐内容所在章节/表格。

5) 对于"缺失章节"（missing_section_check）：列出缺失的章节或子节标题。

6) 最后输出"规则库沉淀清单"：按模块汇总可沉淀为自动规则的条目列表（rule_id + 一句话规则）。

请仅输出一个合法 JSON 对象，包含且仅包含以下两个键：
- "规则校验结果": 上述问题数组（英文键名：issue_id, issue_title, issue_type, severity, location, evidence, rule_definition, norm_basis, fix_suggestion, dependencies）
- "规则库沉淀清单": 数组，每项 {rule_id, rule_summary}

若无问题，则 "规则校验结果" 为 []。"""


def load_norm_lib() -> list:
    """加载规范库（CONS-001 等一致性规则）。"""
    if not os.path.isfile(_NORM_LIB_PATH):
        return []
    try:
        with open(_NORM_LIB_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, list) else []
    except Exception:
        return []


# 每批请求 AI 的规则条数（5～7 条）
BATCH_SIZE_MIN = 5
BATCH_SIZE_MAX = 7


def _batch_rules(rules: list, batch_size: int = 6) -> list[list]:
    """将规则列表按 batch_size 条一批切分，每批 5～7 条。"""
    if not rules:
        return []
    size = max(BATCH_SIZE_MIN, min(BATCH_SIZE_MAX, batch_size))
    return [rules[i : i + size] for i in range(0, len(rules), size)]


def build_rule_engine_messages(doc_content: str, norm_lib_json: str) -> list[dict]:
    """
    构建规则引擎单次调用的消息。
    doc_content: 文档内容（可含 [block_id=xxx] 标注的段落）
    norm_lib_json: 规范库 JSON 字符串（单批或全部规则）
    """
    user_content = f"""【文档内容】
{doc_content[:120000]}

【规范库】
{norm_lib_json}

请根据上述文档内容与规范库，输出规则校验结果与规则库沉淀清单。仅输出一个 JSON 对象，不要其他解释。若无问题，则 "规则校验结果" 为 []。"""
    return [
        {"role": "system", "content": RULE_ENGINE_SYSTEM},
        {"role": "user", "content": user_content},
    ]


def build_rule_engine_messages_batch(
    doc_content: str,
    rules_batch: list[dict],
    batch_index: int,
    total_batches: int,
) -> list[dict]:
    """
    构建单批规则（5～7 条）的请求消息。
    本批仅校验 rules_batch 中的规则，返回也只针对这批规则的校验结果。
    """
    norm_lib_json = json.dumps(rules_batch, ensure_ascii=False, indent=2)
    rule_ids = [r.get("rule_id") or r.get("name") or "" for r in rules_batch]
    user_content = f"""【文档内容】
{doc_content[:120000]}

【本批校验规则】（第 {batch_index + 1}/{total_batches} 批，共 {len(rules_batch)} 条）
规则 ID 列表：{", ".join(rule_ids)}

【规范库】（仅本批规则）
{norm_lib_json}

【重要】文档中每一段格式为：[block_id=xx][page=N] 换行 正文。你发现问题的原文来自某段时，location.page 和 evidence.page_refs 必须填该段的 N（真实页码），不要填 1 或留空。

请仅针对以上 {len(rules_batch)} 条规则，根据文档内容逐条校验。输出一个 JSON 对象：
- "规则校验结果": 本批规则发现的问题数组（每条规则 0 或若干条），格式同前（issue_id, issue_title, issue_type, severity, location, evidence, rule_definition, norm_basis, fix_suggestion, dependencies）
- "规则库沉淀清单": 本批规则的 rule_id + 一句话 rule_summary

若无问题，则 "规则校验结果" 为 []。仅输出 JSON，不要其他解释。"""
    return [
        {"role": "system", "content": RULE_ENGINE_SYSTEM},
        {"role": "user", "content": user_content},
    ]


def get_rule_batches(rules: list, batch_size: int = 6) -> list[list]:
    """对外：将规则列表分成每批 5～7 条的列表。"""
    return _batch_rules(rules, batch_size)
