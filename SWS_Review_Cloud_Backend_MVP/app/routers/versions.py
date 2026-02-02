from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status, Query

from ..models.common import ok_data
from .. import db
from ..services import version_service
from ..storage import get_storage
from ..settings import settings
from ..core.deps import get_current_user, require_project_member, get_project_id_by_version_id

router = APIRouter(prefix="/api", tags=["versions"])
_schema = settings.DB_SCHEMA


def _check_version_access(version_id: int, current_user: dict) -> None:
    project_id = get_project_id_by_version_id(version_id)
    if project_id is None:
        raise HTTPException(status_code=404, detail="Version not found")
    if not require_project_member(project_id, current_user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not a project member")


@router.get("/versions/{version_id}/status", response_model=dict)
def get_version_status(version_id: int, current_user: Annotated[dict, Depends(get_current_user)]):
    _check_version_access(version_id, current_user)
    v = version_service.get_version(version_id)
    if not v:
        raise HTTPException(status_code=404, detail="Version not found")
    return ok_data({"id": v["id"], "status": v["status"], "error_message": v.get("error_message")})


@router.get("/versions/{version_id}/pdf", response_model=dict)
def get_pdf(version_id: int, current_user: Annotated[dict, Depends(get_current_user)]):
    _check_version_access(version_id, current_user)
    sql = f"""
    SELECT dv.id as version_id, fo.storage, fo.object_key, fo.filename
    FROM {_schema}.document_version dv
    LEFT JOIN {_schema}.file_object fo ON fo.id = dv.pdf_file_id
    WHERE dv.id = %(version_id)s
    """
    row = db.fetch_one(sql, {"version_id": version_id})
    if not row:
        raise HTTPException(status_code=404, detail="Version not found")
    # No PDF file linked yet
    if not row.get("object_key") and row.get("storage") is None:
        raise HTTPException(status_code=404, detail="PDF not ready yet")
    # Demo fallback: local storage with object_key pointing to static
    if row.get("storage") == "local" and (row.get("object_key") or "").startswith("demo/"):
        url = f"{settings.BASE_URL.rstrip('/')}/static/demo.pdf"
        return ok_data({"url": url, "filename": row.get("filename") or "demo.pdf"})
    if row.get("object_key"):
        storage = get_storage()
        url = storage.get_signed_url(row["object_key"], expires_in_seconds=1800)
        return ok_data({"url": url, "filename": row.get("filename") or "preview.pdf"})
    raise HTTPException(status_code=404, detail="PDF not ready yet")


@router.get("/versions/{version_id}/outline", response_model=dict)
def get_outline(
    version_id: int,
    current_user: Annotated[dict, Depends(get_current_user)],
):
    _check_version_access(version_id, current_user)
    # 通过 doc_block + block_page_anchor 获取大纲节点对应的 PDF 页码（1-based）
    sql = f"""
    SELECT n.id, n.node_no, n.title, n.level, n.parent_id, n.order_index,
           COALESCE(
             (SELECT bpa.page_no
              FROM {_schema}.doc_block b
              JOIN {_schema}.block_page_anchor bpa ON bpa.block_id = b.id
              WHERE b.outline_node_id = n.id AND b.block_type = 'HEADING'
              ORDER BY bpa.page_no ASC
              LIMIT 1),
             1
           ) AS page_no
    FROM {_schema}.doc_outline_node n
    WHERE n.version_id = %(version_id)s
    ORDER BY n.order_index ASC
    """
    rows = db.fetch_all(sql, {"version_id": version_id})
    return ok_data(rows)


@router.get("/versions/{version_id}/issues", response_model=dict)
def get_issues(
    version_id: int,
    current_user: dict = Depends(get_current_user),
    status: str | None = Query(None),
    severity: str | None = Query(None),
    issue_type: str | None = Query(None),
):
    _check_version_access(version_id, current_user)
    where = ["version_id = %(version_id)s"]
    params = {"version_id": version_id}
    if status:
        where.append("status = %(status)s")
        params["status"] = status
    if severity:
        where.append("severity = %(severity)s")
        params["severity"] = severity
    if issue_type:
        where.append("issue_type = %(issue_type)s")
        params["issue_type"] = issue_type
    sql = f"""
    SELECT id, issue_type, severity, title, description, suggestion, confidence,
           status, page_no, anchor_rects, evidence_quotes, created_at, updated_at
    FROM {_schema}.review_issue
    WHERE {' AND '.join(where)}
    ORDER BY id DESC
    """
    rows = db.fetch_all(sql, params)
    return ok_data(rows)


@router.post("/versions/{version_id}/cancel", response_model=dict)
def cancel_version(version_id: int, current_user: dict = Depends(get_current_user)):
    """取消版本（处理中、待审查、已完成均可取消）"""
    _check_version_access(version_id, current_user)
    v = version_service.get_version(version_id)
    if not v:
        raise HTTPException(status_code=404, detail="Version not found")
    
    if v["status"] not in ("PROCESSING", "READY", "DONE", "UPLOADED"):
        raise HTTPException(
            status_code=400,
            detail=f"Cannot cancel version with status: {v['status']}."
        )
    
    success = version_service.cancel_version(version_id)
    if not success:
        raise HTTPException(status_code=400, detail="Failed to cancel version")
    
    updated_v = version_service.get_version(version_id)
    return ok_data({
        "id": updated_v["id"],
        "status": updated_v["status"],
        "message": "Version canceled successfully"
    })


@router.post("/versions/{version_id}/reprocess", response_model=dict)
def reprocess_version(version_id: int, current_user: dict = Depends(get_current_user)):
    """重新处理版本"""
    _check_version_access(version_id, current_user)
    v = version_service.get_version(version_id)
    if not v:
        raise HTTPException(status_code=404, detail="Version not found")
    
    if not version_service.can_reprocess_version(version_id):
        raise HTTPException(
            status_code=400,
            detail=f"Cannot reprocess version with status: {v['status']}."
        )
    
    success = version_service.reprocess_version(version_id)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to reprocess version. Celery worker may not be available.")
    
    updated_v = version_service.get_version(version_id)
    return ok_data({
        "id": updated_v["id"],
        "status": updated_v["status"],
        "message": "Version reprocessing started"
    })


@router.delete("/versions/{version_id}", response_model=dict)
def delete_version(version_id: int, current_user: dict = Depends(get_current_user)):
    """删除版本及其相关数据"""
    _check_version_access(version_id, current_user)
    v = version_service.get_version(version_id)
    if not v:
        raise HTTPException(status_code=404, detail="Version not found")
    
    if v["status"] == "PROCESSING":
        raise HTTPException(
            status_code=400,
            detail="Cannot delete version that is currently processing. Please cancel it first."
        )
    
    success = version_service.delete_version(version_id)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to delete version")
    
    return ok_data({
        "id": version_id,
        "message": "Version deleted successfully"
    })
