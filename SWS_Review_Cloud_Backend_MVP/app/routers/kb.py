from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File

from ..models.common import ok_data
from ..services import kb_service, file_service
from ..storage import get_storage
from ..core.deps import get_current_user
from ..worker.kb_tasks import index_kb_source_task

router = APIRouter(prefix="/api/kb", tags=["kb"])


@router.post("/sources/upload", response_model=dict)
async def upload_kb_source(
    file: UploadFile = File(...),
    name: str | None = None,
    kb_type: str = "NORM",
    current_user: dict = Depends(get_current_user),
):
    content = await file.read()
    from ..settings import settings
    from ..core.security import content_sha256
    storage = get_storage()
    storage_type = "minio" if settings.STORAGE_TYPE == "minio" else "local"
    bucket = settings.MINIO_BUCKET if storage_type == "minio" else "local"
    key = f"kb/upload/{content_sha256(content[:1000])}/{file.filename or 'source.pdf'}"
    storage.put(key, __import__("io").BytesIO(content), content_type=file.content_type, size=len(content))
    file_id = file_service.create_file_object(storage_type, bucket, key, file.filename or "source.pdf", file.content_type, len(content))
    source_name = name or (file.filename or "未命名")
    source_id = kb_service.create_kb_source(source_name, kb_type, file_id)
    index_kb_source_task.delay(source_id)
    return ok_data({"id": source_id, "name": source_name, "kb_type": kb_type, "status": "PROCESSING"})


@router.get("/sources", response_model=dict)
def list_sources(current_user: Annotated[dict, Depends(get_current_user)]):
    rows = kb_service.list_kb_sources()
    return ok_data(rows)


@router.post("/sources/{source_id}/reindex", response_model=dict)
def reindex_source(source_id: int, current_user: Annotated[dict, Depends(get_current_user)]):
    src = kb_service.get_kb_source(source_id)
    if not src:
        raise HTTPException(status_code=404, detail="Source not found")
    from .. import db
    from ..settings import settings
    schema = settings.DB_SCHEMA
    db.execute(f"UPDATE {schema}.kb_source SET status = 'PROCESSING', error_message = NULL, updated_at = now() WHERE id = %(id)s", {"id": source_id})
    index_kb_source_task.delay(source_id)
    return ok_data({"id": source_id, "status": "PROCESSING"})
