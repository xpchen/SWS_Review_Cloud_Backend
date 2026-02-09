from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status, Query
from fastapi.responses import StreamingResponse

from ..models.common import ok_data
from ..services.export_service import build_issues_xlsx, build_issues_docx
from ..core.deps import get_current_user, require_project_member, get_project_id_by_version_id

router = APIRouter(prefix="/api", tags=["export"])


def _export_issues_xlsx_response(version_id: int, status: str | None, severity: str | None):
    data = build_issues_xlsx(version_id, status=status, severity=severity)
    return StreamingResponse(
        iter([data]),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=issues.xlsx"},
    )


def _export_issues_docx_response(version_id: int, status: str | None, severity: str | None):
    """导出 Word 问题清单（审查错误统计表 + 按大纲分组的问题列表）。"""
    data = build_issues_docx(version_id, status=status, severity=severity)
    return StreamingResponse(
        iter([data]),
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"Content-Disposition": 'attachment; filename="问题清单.docx"'},
    )


@router.post("/versions/{version_id}/export")
def export_issues_post(
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
    if type == "issues.docx":
        return _export_issues_docx_response(version_id, status, severity)
    if type != "issues.xlsx":
        raise HTTPException(status_code=400, detail="Only type=issues.xlsx or type=issues.docx is supported")
    return _export_issues_xlsx_response(version_id, status, severity)


@router.get("/versions/{version_id}/export")
def export_issues_get(
    version_id: int,
    current_user: dict = Depends(get_current_user),
    type: str = Query("issues.xlsx", alias="type"),
    status: str | None = Query(None),
    severity: str | None = Query(None),
):
    """GET 导出审查结果。type=issues.xlsx 为 Excel；type=issues.docx 为 Word 问题清单。"""
    project_id = get_project_id_by_version_id(version_id)
    if project_id is None:
        raise HTTPException(status_code=404, detail="Version not found")
    if not require_project_member(project_id, current_user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not a project member")
    if type == "issues.docx":
        return _export_issues_docx_response(version_id, status, severity)
    return _export_issues_xlsx_response(version_id, status, severity)
