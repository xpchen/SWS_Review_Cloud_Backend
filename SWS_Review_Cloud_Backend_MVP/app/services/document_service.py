from .. import db
from ..settings import settings

_schema = settings.DB_SCHEMA


def list_documents(project_id: int) -> list[dict]:
    sql = f"""
    SELECT id, project_id, doc_type, title, current_version_id, created_at, updated_at
    FROM {_schema}.document
    WHERE project_id = %(project_id)s
    ORDER BY id DESC
    """
    return db.fetch_all(sql, {"project_id": project_id})


def list_documents_with_status(project_id: int) -> list[dict]:
    """列表带最新版本状态、审查进度、问题条数，供前端展示处理进度/状态/结果。"""
    sql = f"""
    SELECT d.id, d.project_id, d.doc_type, d.title, d.current_version_id, d.created_at, d.updated_at,
           dv.id AS version_id,
           dv.status AS version_status,
           dv.error_message AS version_error_message,
           COALESCE(rr.progress, 0) AS run_progress,
           rr.status AS run_status,
           COALESCE(ic.issue_count, 0)::int AS issue_count
    FROM {_schema}.document d
    LEFT JOIN {_schema}.document_version dv ON dv.id = d.current_version_id
    LEFT JOIN LATERAL (
        SELECT id, version_id, status, progress
        FROM {_schema}.review_run
        WHERE version_id = dv.id
        ORDER BY id DESC
        LIMIT 1
    ) rr ON rr.version_id = dv.id
    LEFT JOIN LATERAL (
        SELECT version_id, COUNT(*) AS issue_count
        FROM {_schema}.review_issue
        WHERE version_id = dv.id
        GROUP BY version_id
    ) ic ON ic.version_id = dv.id
    WHERE d.project_id = %(project_id)s
    ORDER BY d.id DESC
    """
    return db.fetch_all(sql, {"project_id": project_id})


def create_document(project_id: int, title: str, doc_type: str = "SOIL_WATER_PLAN") -> int:
    sql = f"""
    INSERT INTO {_schema}.document (project_id, title, doc_type)
    VALUES (%(project_id)s, %(title)s, %(doc_type)s)
    RETURNING id
    """
    with db.pool.connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, {"project_id": project_id, "title": title, "doc_type": doc_type})
            row = cur.fetchone()
            return row[0]


def get_document(document_id: int) -> dict | None:
    sql = f"""
    SELECT id, project_id, doc_type, title, current_version_id
    FROM {_schema}.document
    WHERE id = %(document_id)s
    """
    return db.fetch_one(sql, {"document_id": document_id})


def list_versions(document_id: int) -> list[dict]:
    sql = f"""
    SELECT id, document_id, version_no, status, source_file_id, pdf_file_id,
           structure_json_file_id, page_map_json_file_id, error_message, created_at
    FROM {_schema}.document_version
    WHERE document_id = %(document_id)s
    ORDER BY version_no DESC
    """
    return db.fetch_all(sql, {"document_id": document_id})


def set_current_version(document_id: int, version_id: int) -> None:
    sql = f"""
    UPDATE {_schema}.document SET current_version_id = %(version_id)s, updated_at = now()
    WHERE id = %(document_id)s
    """
    db.execute(sql, {"document_id": document_id, "version_id": version_id})


def delete_document(document_id: int) -> bool:
    """删除文档及其所有版本"""
    doc = get_document(document_id)
    if not doc:
        return False

    from . import version_service
    versions = list_versions(document_id)
    for v in versions:
        if v.get("status") == "PROCESSING":
            return False  # 不能删除包含处理中版本的文档

    with db.pool.connection() as conn:
        with conn.cursor() as cur:
            for v in versions:
                vid = v["id"]
                cur.execute(f"DELETE FROM {_schema}.review_issue WHERE version_id = %(vid)s", {"vid": vid})
                cur.execute(f"DELETE FROM {_schema}.review_run WHERE version_id = %(vid)s", {"vid": vid})
                cur.execute(f"DELETE FROM {_schema}.doc_block WHERE version_id = %(vid)s", {"vid": vid})
                cur.execute(f"DELETE FROM {_schema}.doc_table WHERE version_id = %(vid)s", {"vid": vid})
                cur.execute(f"DELETE FROM {_schema}.doc_outline_node WHERE version_id = %(vid)s", {"vid": vid})
                cur.execute(f"DELETE FROM {_schema}.doc_fact WHERE version_id = %(vid)s", {"vid": vid})
                cur.execute(f"DELETE FROM {_schema}.document_version WHERE id = %(vid)s", {"vid": vid})
            cur.execute(f"DELETE FROM {_schema}.document WHERE id = %(document_id)s", {"document_id": document_id})
            conn.commit()
            return True
