from dataclasses import dataclass
from typing import Any


@dataclass
class IssueDraft:
    issue_type: str
    severity: str  # S1/S2/S3
    title: str
    description: str
    suggestion: str
    confidence: float
    evidence_block_ids: list[int]
    page_no: int | None = None  # 允许None，会在insert_issue时从block_page_anchor反查
    anchor_rects: list[dict[str, Any]] | None = None
    evidence_quotes: list[dict[str, Any]] | None = None


def run_rule(version_id: int, rule_config: dict) -> list["IssueDraft"]:
    """Base: override in each rule. Input version_id + checkpoint.rule_config_json -> IssueDraft list."""
    return []
