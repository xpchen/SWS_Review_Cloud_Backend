from .. import db
from ..settings import settings

_schema = settings.DB_SCHEMA


def create_project(name: str, owner_user_id: int, location: str | None = None) -> int:
    sql = f"""
    INSERT INTO {_schema}.project (name, location, owner_user_id)
    VALUES (%(name)s, %(location)s, %(owner_user_id)s)
    RETURNING id
    """
    with db.pool.connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, {"name": name, "location": location, "owner_user_id": owner_user_id})
            row = cur.fetchone()
            pid = row[0]
    # add owner as project_member
    sql2 = f"""
    INSERT INTO {_schema}.project_member (project_id, user_id, project_role)
    VALUES (%(project_id)s, %(user_id)s, 'owner')
    """
    db.execute(sql2, {"project_id": pid, "user_id": owner_user_id})
    return pid


def list_projects(user_id: int) -> list[dict]:
    sql = f"""
    SELECT p.id, p.name, p.location, p.owner_user_id
    FROM {_schema}.project p
    JOIN {_schema}.project_member pm ON pm.project_id = p.id
    WHERE pm.user_id = %(user_id)s
    ORDER BY p.id DESC
    """
    return db.fetch_all(sql, {"user_id": user_id})


def get_project(project_id: int) -> dict | None:
    sql = f"""
    SELECT id, name, location, owner_user_id
    FROM {_schema}.project
    WHERE id = %(project_id)s
    """
    return db.fetch_one(sql, {"project_id": project_id})
