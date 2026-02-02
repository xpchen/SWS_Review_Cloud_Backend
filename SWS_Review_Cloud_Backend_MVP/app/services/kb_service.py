from .. import db
from ..settings import settings

_schema = settings.DB_SCHEMA


def create_kb_source(name: str, kb_type: str, file_id: int) -> int:
    sql = f"""
    INSERT INTO {_schema}.kb_source (name, kb_type, file_id, status)
    VALUES (%(name)s, %(kb_type)s, %(file_id)s, 'PROCESSING')
    RETURNING id
    """
    with db.pool.connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, {"name": name, "kb_type": kb_type, "file_id": file_id})
            return cur.fetchone()[0]


def list_kb_sources() -> list[dict]:
    sql = f"""
    SELECT id, name, kb_type, file_id, status, error_message, created_at
    FROM {_schema}.kb_source
    ORDER BY id DESC
    """
    return db.fetch_all(sql, {})


def get_kb_source(source_id: int) -> dict | None:
    sql = f"""
    SELECT id, name, kb_type, file_id, status, error_message
    FROM {_schema}.kb_source
    WHERE id = %(source_id)s
    """
    return db.fetch_one(sql, {"source_id": source_id})


def set_kb_source_ready(source_id: int) -> None:
    sql = f"UPDATE {_schema}.kb_source SET status = 'READY', updated_at = now() WHERE id = %(source_id)s"
    db.execute(sql, {"source_id": source_id})


def set_kb_source_failed(source_id: int, error_message: str) -> None:
    sql = f"UPDATE {_schema}.kb_source SET status = 'FAILED', error_message = %(msg)s, updated_at = now() WHERE id = %(source_id)s"
    db.execute(sql, {"source_id": source_id, "msg": error_message[:2000]})


def insert_chunk(kb_source_id: int, chunk_text: str, meta_json: dict | None, hash_val: str, embedding: list[float] | None = None) -> int | None:
    """
    插入chunk，支持embedding向量
    
    Args:
        kb_source_id: 知识库源ID
        chunk_text: chunk文本
        meta_json: 元数据JSON
        hash_val: chunk的hash值
        embedding: embedding向量（1024维），可选
    """
    import json
    # 检查embedding列是否存在（向后兼容）
    has_embedding_col = True  # 假设已执行005迁移
    fields = ["kb_source_id", "chunk_text", "meta_json", "hash"]
    values = ["%(kb_source_id)s", "%(chunk_text)s", "%(meta_json)s", "%(hash)s"]
    
    if embedding is not None and has_embedding_col:
        fields.append("embedding")
        values.append("%(embedding)s")
    
    sql = f"""
    INSERT INTO {_schema}.kb_chunk ({', '.join(fields)})
    VALUES ({', '.join(values)})
    ON CONFLICT (kb_source_id, hash) DO NOTHING
    RETURNING id
    """
    with db.pool.connection() as conn:
        with conn.cursor() as cur:
            params = {
                "kb_source_id": kb_source_id,
                "chunk_text": chunk_text[:10000],
                "meta_json": json.dumps(meta_json or {}),
                "hash": hash_val,
            }
            if embedding is not None and has_embedding_col:
                # 将list转换为PostgreSQL的vector类型
                params["embedding"] = str(embedding)  # psycopg会自动转换
            try:
                cur.execute(sql, params)
                row = cur.fetchone()
                return row[0] if row else None
            except Exception as e:
                # 如果embedding列不存在，尝试不带embedding的版本
                if embedding is not None and "embedding" in str(e).lower():
                    fields_no_emb = [f for f in fields if f != "embedding"]
                    values_no_emb = [v for v in values if "embedding" not in v]
                    sql_fallback = f"""
                    INSERT INTO {_schema}.kb_chunk ({', '.join(fields_no_emb)})
                    VALUES ({', '.join(values_no_emb)})
                    ON CONFLICT (kb_source_id, hash) DO NOTHING
                    RETURNING id
                    """
                    params_no_emb = {k: v for k, v in params.items() if k != "embedding"}
                    cur.execute(sql_fallback, params_no_emb)
                    row = cur.fetchone()
                    return row[0] if row else None
                raise
