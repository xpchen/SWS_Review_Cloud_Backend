from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status, Query
from fastapi.responses import StreamingResponse

from ..models.common import ok_data
from ..services.export_service import build_issues_xlsx
from ..core.deps import get_current_user, require_project_member, get_project_id_by_version_id

router = APIRouter(prefix="/api", tags=["export"])


@router.post("/versions/{version_id}/export")
def export_issues(
    version_id: int,
    current_user: dict = Depends(get_current_user),
    type: str = Query("issues.xlsx", alias="type"),
    status: str | None = Query(None),
    severity: str | None = Query(None),
):
    project_id = get_project_id_by_version_id(version_id)
    if project_id is None:
        raise HTTPException(status_code=404, detail="Version not found")
    if not require_project_member(project_id, current_user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not a project member")
    if type != "issues.xlsx":
        raise HTTPException(status_code=400, detail="Only type=issues.xlsx is supported")
    data = build_issues_xlsx(version_id, status=status, severity=severity)
    return StreamingResponse(
        iter([data]),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=issues.xlsx"},
    )
