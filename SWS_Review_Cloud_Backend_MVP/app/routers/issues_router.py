from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from ..models.common import ok_data
from ..models.review import IssueActionRequest
from ..services.issue_service import get_issue, apply_action
from ..core.deps import get_current_user, require_project_member, get_project_id_by_issue_id

router = APIRouter(prefix="/api", tags=["issues"])


@router.get("/issues/{issue_id}", response_model=dict)
def get_issue_detail(issue_id: int, current_user: Annotated[dict, Depends(get_current_user)]):
    project_id = get_project_id_by_issue_id(issue_id)
    if project_id is None:
        raise HTTPException(status_code=404, detail="Issue not found")
    if not require_project_member(project_id, current_user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not a project member")
    issue = get_issue(issue_id)
    if not issue:
        raise HTTPException(status_code=404, detail="Issue not found")
    return ok_data(issue)


@router.post("/issues/{issue_id}/actions", response_model=dict)
def issue_action(
    issue_id: int,
    body: IssueActionRequest,
    current_user: Annotated[dict, Depends(get_current_user)],
):
    project_id = get_project_id_by_issue_id(issue_id)
    if project_id is None:
        raise HTTPException(status_code=404, detail="Issue not found")
    if not require_project_member(project_id, current_user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not a project member")
    ok = apply_action(issue_id, body.action, current_user["id"], body.action_reason)
    if not ok:
        raise HTTPException(status_code=400, detail="Invalid action")
    issue = get_issue(issue_id)
    return ok_data(issue)
