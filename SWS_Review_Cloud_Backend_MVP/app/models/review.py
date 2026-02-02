from typing import Any

from pydantic import BaseModel


class ReviewRunCreate(BaseModel):
    run_type: str  # RULE | AI | MIXED


class ReviewRunOut(BaseModel):
    id: int
    version_id: int
    run_type: str
    status: str
    progress: int
    started_at: str | None
    finished_at: str | None
    error_message: str | None


class IssueActionRequest(BaseModel):
    action: str  # ACCEPT | IGNORE | FIX | COMMENT
    action_reason: str | None = None


class IssueOut(BaseModel):
    id: int
    issue_type: str
    severity: str
    title: str
    description: str | None
    suggestion: str | None
    confidence: float
    status: str
    page_no: int | None
    evidence_quotes: list[Any] | None
    anchor_rects: list[Any] | None
    created_at: Any
    updated_at: Any
