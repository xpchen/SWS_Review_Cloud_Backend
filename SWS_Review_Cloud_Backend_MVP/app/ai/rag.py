from .. import db
from ..settings import settings

_schema = settings.DB_SCHEMA


def search_chunks(query: str, top_k: int = 10, kb_source_ids: list[int] | None = None) -> list[dict]:
    """Simple text search on kb_chunk (LIKE). MVP: no embedding."""
    where = [f"c.kb_source_id IN (SELECT id FROM {_schema}.kb_source WHERE status = 'READY')", "c.chunk_text ILIKE %(q)s"]
    params = {"q": f"%{query}%", "top_k": top_k}
    if kb_source_ids:
        where.append("c.kb_source_id = ANY(%(ids)s)")
        params["ids"] = kb_source_ids
    sql = f"""
    SELECT c.id, c.kb_source_id, c.chunk_text, c.meta_json, c.hash
    FROM {_schema}.kb_chunk c
    WHERE {' AND '.join(where)}
    LIMIT %(top_k)s
    """
    return db.fetch_all(sql, params)
