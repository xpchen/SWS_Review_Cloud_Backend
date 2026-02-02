from .. import db
from ..settings import settings

_schema = settings.DB_SCHEMA


def create_file_object(
    storage: str,
    bucket: str,
    object_key: str,
    filename: str,
    content_type: str | None = None,
    size: int = 0,
    sha256: str | None = None,
) -> int:
    sql = f"""
    INSERT INTO {_schema}.file_object (storage, bucket, object_key, filename, content_type, size, sha256)
    VALUES (%(storage)s, %(bucket)s, %(object_key)s, %(filename)s, %(content_type)s, %(size)s, %(sha256)s)
    RETURNING id
    """
    with db.pool.connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, {
                "storage": storage,
                "bucket": bucket,
                "object_key": object_key,
                "filename": filename,
                "content_type": content_type,
                "size": size,
                "sha256": sha256,
            })
            row = cur.fetchone()
            return row[0]


def get_file_object(file_id: int) -> dict | None:
    sql = f"""
    SELECT id, storage, bucket, object_key, filename, content_type, size
    FROM {_schema}.file_object
    WHERE id = %(file_id)s
    """
    return db.fetch_one(sql, {"file_id": file_id})
