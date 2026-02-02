import io
import logging
from typing import BinaryIO

from ..storage import get_storage
from .. import db
from ..core.security import content_sha256
from ..settings import settings
from .file_service import create_file_object
from .version_service import create_version, get_next_version_no, update_version_status
from .document_service import set_current_version

logger = logging.getLogger(__name__)

_schema = settings.DB_SCHEMA
MAX_DOCX_SIZE = 50 * 1024 * 1024  # 50MB
ALLOWED_CONTENT = (
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/octet-stream",
)


def upload_docx(
    document_id: int,
    file_content: bytes,
    filename: str,
    content_type: str | None,
    trigger_pipeline: bool = True,
) -> dict:
    """Validate, store, create file_object and document_version. Optionally trigger pipeline (when worker exists)."""
    if len(file_content) > MAX_DOCX_SIZE:
        raise ValueError("File too large")
    if content_type and content_type not in ALLOWED_CONTENT:
        if not (filename and filename.lower().endswith(".docx")):
            raise ValueError("Only .docx files are allowed")
    storage = get_storage()
    storage_type = "minio" if settings.STORAGE_TYPE == "minio" else "local"
    bucket = settings.MINIO_BUCKET if storage_type == "minio" else "local"

    version_no = get_next_version_no(document_id)
    # We need version_id for key but we create version after file_object. So: create version first with status PROCESSING and source_file_id placeholder? No - we need source_file_id. So create file_object first with a temp key, then create version, then we could rename key. Actually DDS key is projects/{project_id}/documents/{document_id}/versions/{version_id}/source.docx - so we need version_id. So we have two options: 1) Create version with a dummy source_file_id (e.g. 0) then update after file_object. 2) Use a temporary key then move. 3) Create version with version_no and get next id by inserting and returning. So: insert version with source_file_id = 0 is invalid (FK). So we must insert file_object first. Key could be projects/p/document/d/versions/v/source.docx - but we don't have v until we create version. So use: create file_object with key that includes document_id and version_no (which is unique per doc): projects/{project_id}/documents/{document_id}/versions/v{version_no}/source.docx. Then create version with that source_file_id. Later when we have version_id we don't need to change the key - the key in DDS can be interpreted as version_no for simplicity, or we add a column. Actually DDS says versions/{version_id}/source.docx - so version_id is numeric. So we have to either reserve an id or use a two-step: insert version returning id with a placeholder source_file_id - but FK requires real file_object. So the only way is: insert file_object with a key that uses version_no: projects/.../versions/{version_no}/source.docx (and we'll never overwrite since version_no increments). Then insert version. So key = f"projects/{project_id}/documents/{document_id}/versions/{version_no}/source.docx"
    doc = db.fetch_one(f"SELECT project_id FROM {_schema}.document WHERE id = %(document_id)s", {"document_id": document_id})
    if not doc:
        raise ValueError("Document not found")
    project_id = doc["project_id"]
    object_key = f"projects/{project_id}/documents/{document_id}/versions/{version_no}/source.docx"

    file_like = io.BytesIO(file_content)
    storage.put(object_key, file_like, content_type=content_type or "application/vnd.openxmlformats-officedocument.wordprocessingml.document", size=len(file_content))
    sha = content_sha256(file_content)
    file_id = create_file_object(
        storage=storage_type,
        bucket=bucket,
        object_key=object_key,
        filename=filename or "document.docx",
        content_type=content_type,
        size=len(file_content),
        sha256=sha,
    )
    status = "PROCESSING" if trigger_pipeline else "UPLOADED"
    version_id = create_version(document_id=document_id, version_no=version_no, source_file_id=file_id, status=status)
    set_current_version(document_id, version_id)

    # 触发处理管道
    if trigger_pipeline:
        try:
            from ..worker.tasks import pipeline_chain
            logger.info(f"[版本 {version_id}] 触发处理管道")
            result = pipeline_chain.delay(version_id)
            logger.info(f"[版本 {version_id}] ✅ 任务已提交到 Celery，任务ID: {result.id if result else 'N/A'}")
        except ImportError as e:
            error_msg = f"无法导入 Celery 任务模块: {e}"
            logger.error(f"[版本 {version_id}] ❌ {error_msg}")
            update_version_status(version_id, "FAILED", error_message=error_msg)
            status = "FAILED"
        except Exception as e:
            error_msg = f"触发处理管道失败: {e}"
            logger.error(f"[版本 {version_id}] ❌ {error_msg}", exc_info=True)
            # 检查是否是 Celery broker 连接问题
            error_str = str(e).lower()
            if "connection" in error_str or "broker" in error_str or "redis" in error_str:
                error_msg = f"Celery worker 未运行或 Redis 连接失败: {e}"
            update_version_status(version_id, "FAILED", error_message=error_msg[:500])
            status = "FAILED"

    return {"version_id": version_id, "version_no": version_no, "status": status}
