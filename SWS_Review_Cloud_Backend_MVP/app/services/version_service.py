import logging
from .. import db
from ..settings import settings

_schema = settings.DB_SCHEMA
logger = logging.getLogger(__name__)


def get_next_version_no(document_id: int) -> int:
    sql = f"""
    SELECT COALESCE(MAX(version_no), 0) + 1 AS next_version_no
    FROM {_schema}.document_version
    WHERE document_id = %(document_id)s
    """
    row = db.fetch_one(sql, {"document_id": document_id})
    return row["next_version_no"] if row else 1


def create_version(
    document_id: int,
    version_no: int,
    source_file_id: int,
    status: str = "UPLOADED",
) -> int:
    sql = f"""
    INSERT INTO {_schema}.document_version (document_id, version_no, status, source_file_id)
    VALUES (%(document_id)s, %(version_no)s, %(status)s, %(source_file_id)s)
    RETURNING id
    """
    with db.pool.connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, {
                "document_id": document_id,
                "version_no": version_no,
                "status": status,
                "source_file_id": source_file_id,
            })
            row = cur.fetchone()
            return row[0]


def get_version(version_id: int) -> dict | None:
    """
    获取版本信息，包含进度和当前步骤
    """
    sql = f"""
    SELECT id, document_id, version_no, status, source_file_id, pdf_file_id,
           structure_json_file_id, page_map_json_file_id, text_full_file_id,
           error_message, created_at, updated_at,
           COALESCE(progress, 0) as progress,
           current_step
    FROM {_schema}.document_version
    WHERE id = %(version_id)s
    """
    return db.fetch_one(sql, {"version_id": version_id})


def update_version_status(
    version_id: int, 
    status: str, 
    error_message: str | None = None,
    progress: int | None = None,
    current_step: str | None = None
) -> None:
    """
    更新版本状态
    
    Args:
        version_id: 版本ID
        status: 状态
        error_message: 错误消息（可选）
        progress: 进度百分比 0-100（可选）
        current_step: 当前步骤描述（可选）
    """
    sql = f"""
    UPDATE {_schema}.document_version
    SET status = %(status)s, updated_at = now()
    """
    params = {"version_id": version_id, "status": status}
    if error_message is not None:
        sql += ", error_message = %(error_message)s"
        params["error_message"] = error_message
    if progress is not None:
        sql += ", progress = %(progress)s"
        params["progress"] = progress
    if current_step is not None:
        sql += ", current_step = %(current_step)s"
        params["current_step"] = current_step
    sql += " WHERE id = %(version_id)s"
    db.execute(sql, params)
    
    # 输出日志
    status_msg = f"[版本 {version_id}] 状态更新: {status}"
    if progress is not None:
        status_msg += f", 进度: {progress}%"
    if current_step:
        status_msg += f", 步骤: {current_step}"
    logger.info(status_msg)
    import sys
    print(status_msg, file=sys.stderr, flush=True)


def set_version_pdf_file(version_id: int, pdf_file_id: int) -> None:
    sql = f"""
    UPDATE {_schema}.document_version SET pdf_file_id = %(pdf_file_id)s, updated_at = now()
    WHERE id = %(version_id)s
    """
    db.execute(sql, {"version_id": version_id, "pdf_file_id": pdf_file_id})


def set_version_structure_file(version_id: int, file_id: int) -> None:
    sql = f"""
    UPDATE {_schema}.document_version SET structure_json_file_id = %(file_id)s, updated_at = now()
    WHERE id = %(version_id)s
    """
    db.execute(sql, {"version_id": version_id, "file_id": file_id})


def set_version_page_map_file(version_id: int, file_id: int) -> None:
    sql = f"""
    UPDATE {_schema}.document_version SET page_map_json_file_id = %(file_id)s, updated_at = now()
    WHERE id = %(version_id)s
    """
    db.execute(sql, {"version_id": version_id, "file_id": file_id})


def cancel_version(version_id: int) -> bool:
    """取消版本（处理中、待审查、已完成均可取消，将状态改为 CANCELED）"""
    sql = f"""
    UPDATE {_schema}.document_version
    SET status = 'CANCELED', updated_at = now(), error_message = NULL
    WHERE id = %(version_id)s AND status IN ('PROCESSING', 'READY', 'DONE', 'UPLOADED')
    """
    with db.pool.connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, {"version_id": version_id})
            return cur.rowcount > 0


def can_reprocess_version(version_id: int) -> bool:
    """检查版本是否可以重新处理（状态为 FAILED, CANCELED, READY, UPLOADED, DONE）"""
    v = get_version(version_id)
    if not v:
        return False
    status = v.get("status", "")
    return status in ("FAILED", "CANCELED", "READY", "UPLOADED", "DONE")


def reprocess_version(version_id: int) -> bool:
    """重新处理版本：重置状态为 PROCESSING 并触发 pipeline"""
    v = get_version(version_id)
    if not v:
        return False
    
    # 检查是否可以重新处理
    if not can_reprocess_version(version_id):
        return False
    
    # 更新状态为 PROCESSING
    update_version_status(version_id, "PROCESSING", error_message=None)
    
    # 触发 pipeline
    try:
        from ..worker.tasks import pipeline_chain
        pipeline_chain.delay(version_id)
        return True
    except Exception:
        # 如果 Celery 不可用，将状态改回原状态
        update_version_status(version_id, v["status"], error_message="Celery worker not available")
        return False


def delete_version(version_id: int) -> bool:
    """删除版本及其相关数据"""
    v = get_version(version_id)
    if not v:
        return False
    
    # 检查是否可以删除（不能删除正在处理的版本）
    if v.get("status") == "PROCESSING":
        return False
    
    with db.pool.connection() as conn:
        with conn.cursor() as cur:
            # 删除相关数据（按依赖顺序）
            # 1. 删除审查问题
            cur.execute(f"DELETE FROM {_schema}.review_issue WHERE version_id = %(version_id)s", {"version_id": version_id})
            
            # 2. 删除审查运行
            cur.execute(f"DELETE FROM {_schema}.review_run WHERE version_id = %(version_id)s", {"version_id": version_id})
            
            # 3. 删除文档块
            cur.execute(f"DELETE FROM {_schema}.doc_block WHERE version_id = %(version_id)s", {"version_id": version_id})
            
            # 4. 删除文档表格
            cur.execute(f"DELETE FROM {_schema}.doc_table WHERE version_id = %(version_id)s", {"version_id": version_id})
            
            # 5. 删除文档大纲节点
            cur.execute(f"DELETE FROM {_schema}.doc_outline_node WHERE version_id = %(version_id)s", {"version_id": version_id})
            
            # 6. 删除文档事实
            cur.execute(f"DELETE FROM {_schema}.doc_fact WHERE version_id = %(version_id)s", {"version_id": version_id})
            
            # 7. 删除版本本身
            cur.execute(f"DELETE FROM {_schema}.document_version WHERE id = %(version_id)s", {"version_id": version_id})
            
            # 注意：file_object 记录保留（可能被其他版本引用，或者需要手动清理存储）
            
            conn.commit()
            return True
