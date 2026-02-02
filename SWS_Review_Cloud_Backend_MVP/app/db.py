from psycopg_pool import ConnectionPool
from .settings import settings

pool = ConnectionPool(conninfo=settings.DATABASE_URL, min_size=1, max_size=10, kwargs={"autocommit": True})

def fetch_all(sql: str, params: dict | None = None):
    with pool.connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params or {})
            cols = [d.name for d in cur.description] if cur.description else []
            rows = cur.fetchall()
            return [dict(zip(cols, r)) for r in rows]

def fetch_one(sql: str, params: dict | None = None):
    with pool.connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params or {})
            cols = [d.name for d in cur.description] if cur.description else []
            row = cur.fetchone()
            return dict(zip(cols, row)) if row else None

def execute(sql: str, params: dict | None = None) -> None:
    with pool.connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params or {})

def execute_returning(sql: str, params: dict | None = None, returning: str = "id"):
    """Execute INSERT/UPDATE ... RETURNING id; returns the returned value."""
    with pool.connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params or {})
            row = cur.fetchone()
            return row[0] if row else None

def executemany(sql: str, params_list: list[dict]) -> None:
    """Execute SQL with multiple parameter sets (batch insert/update)."""
    if not params_list:
        return
    with pool.connection() as conn:
        with conn.cursor() as cur:
            cur.executemany(sql, params_list)
