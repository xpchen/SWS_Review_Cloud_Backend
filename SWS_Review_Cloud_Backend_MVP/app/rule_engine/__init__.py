import logging
from .base import IssueDraft, run_rule
from .sum_mismatch import run_sum_mismatch
from .unit_inconsistent import run_unit_inconsistent
from .missing_section import run_missing_section
from .key_field_inconsistent import run_key_field_inconsistent
from .format_review import run_format_review
from .content_review import run_content_review
from .consistency_review import run_consistency_review
from .business_logic_review import run_business_logic_review
from .formula_calculation import run_formula_calculation
from .. import db
from ..settings import settings
from ..services.checkpoint_runner import build_context, run_checkpoints

_schema = settings.DB_SCHEMA
logger = logging.getLogger(__name__)

# 执行器注册表：executor名称 -> 执行函数
EXECUTOR_REGISTRY = {
    # 格式审查
    "format_review": run_format_review,
    # 内容审查
    "content_review": run_content_review,
    # 一致性审查
    "consistency_review": run_consistency_review,
    # 表内计算
    "sum_mismatch": run_sum_mismatch,
    # 公式计算
    "formula_calculation": run_formula_calculation,
    # 业务逻辑
    "business_logic_review": run_business_logic_review,
    # 旧规则（向后兼容）
    "unit_inconsistent": run_unit_inconsistent,
    "missing_section": run_missing_section,
    "key_field_inconsistent": run_key_field_inconsistent,
    # 向后兼容：保留旧的code映射
    "SUM_MISMATCH": run_sum_mismatch,
    "UNIT_INCONSISTENT": run_unit_inconsistent,
    "MISSING_SECTION": run_missing_section,
    "KEY_FIELD_INCONSISTENT": run_key_field_inconsistent,
    # 修复cp_前缀的executor名称
    "cp_sum_mismatch": run_sum_mismatch,
    "cp_unit_inconsistent": run_unit_inconsistent,
    "cp_missing_section": run_missing_section,
}


def run_all_rules(version_id: int, run_id: int | None = None) -> list[tuple["IssueDraft", str]]:
    """
    从review_checkpoint读取启用的规则配置，按executor分发执行。
    返回(IssueDraft, checkpoint_code)列表，便于绑定checkpoint_code。
    
    注意：此函数已迁移到checkpoint_runner，保留此函数用于向后兼容。
    新代码应直接使用checkpoint_runner.run_checkpoints。
    """
    # 构建执行上下文
    context = build_context(version_id)
    
    # 使用checkpoint_runner执行RULE类型的checkpoint
    return run_checkpoints(context, "RULE", EXECUTOR_REGISTRY)
