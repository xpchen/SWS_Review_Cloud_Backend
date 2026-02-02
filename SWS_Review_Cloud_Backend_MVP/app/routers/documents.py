from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File

from ..models.documents import DocumentCreate
from ..models.common import ok_data
from ..services import document_service, upload_service
from ..core.deps import get_current_user, require_project_member

router = APIRouter(prefix="/api", tags=["documents"])


@router.post("/projects/{project_id}/documents", response_model=dict)
def create_document(project_id: int, body: DocumentCreate, current_user: Annotated[dict, Depends(get_current_user)]):
    if not require_project_member(project_id, current_user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not a project member")
    doc_id = document_service.create_document(project_id, body.title, body.doc_type)
    doc = document_service.get_document(doc_id)
    return ok_data(doc)


@router.get("/projects/{project_id}/documents", response_model=dict)
def list_documents(project_id: int, current_user: Annotated[dict, Depends(get_current_user)]):
    if not require_project_member(project_id, current_user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not a project member")
    rows = document_service.list_documents(project_id)
    return ok_data(rows)


@router.get("/documents/{document_id}", response_model=dict)
def get_document(document_id: int, current_user: Annotated[dict, Depends(get_current_user)]):
    doc = document_service.get_document(document_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    if not require_project_member(doc["project_id"], current_user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not a project member")
    return ok_data(doc)


@router.get("/documents/{document_id}/versions", response_model=dict)
def list_versions(document_id: int, current_user: Annotated[dict, Depends(get_current_user)]):
    doc = document_service.get_document(document_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    if not require_project_member(doc["project_id"], current_user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not a project member")
    rows = document_service.list_versions(document_id)
    return ok_data(rows)


@router.delete("/documents/{document_id}", response_model=dict)
def delete_document_endpoint(document_id: int, current_user: Annotated[dict, Depends(get_current_user)]):
    """删除文档及其所有版本"""
    doc = document_service.get_document(document_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    if not require_project_member(doc["project_id"], current_user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not a project member")
    success = document_service.delete_document(document_id)
    if not success:
        raise HTTPException(
            status_code=400,
            detail="Cannot delete document with version currently processing. Please cancel it first."
        )
    return ok_data({"id": document_id, "message": "Document deleted successfully"})


@router.post("/documents/{document_id}/versions/upload", response_model=dict)
async def upload_version(
    document_id: int,
    file: UploadFile = File(...),
    current_user: dict = Depends(get_current_user),
):
    doc = document_service.get_document(document_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    if not require_project_member(doc["project_id"], current_user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not a project member")
    content = await file.read()
    try:
        result = upload_service.upload_docx(
            document_id,
            content,
            file.filename or "document.docx",
            file.content_type,
            trigger_pipeline=True,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return ok_data(result)
