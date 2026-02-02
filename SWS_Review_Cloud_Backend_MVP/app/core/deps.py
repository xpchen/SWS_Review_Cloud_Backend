from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from .. import db
from ..settings import settings
from .security import decode_token

_schema = settings.DB_SCHEMA
_bearer = HTTPBearer(auto_error=False)


def get_current_user(
    creds: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
) -> dict:
    if not creds:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    payload = decode_token(creds.credentials)
    if not payload or payload.get("type") != "access":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        )
    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    try:
        uid = int(user_id)
    except (TypeError, ValueError):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    sql = f"""
    SELECT id, username, display_name, status
    FROM {_schema}.sys_user
    WHERE id = %(user_id)s AND status = 'active'
    """
    user = db.fetch_one(sql, {"user_id": uid})
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found or inactive")
    return user


def require_project_member(
    project_id: int,
    current_user: dict,
    min_role: str | None = "viewer",
) -> bool:
    """Check current_user is member of project. Role order: owner > editor > reviewer > viewer."""
    sql = f"""
    SELECT project_role FROM {_schema}.project_member
    WHERE project_id = %(project_id)s AND user_id = %(user_id)s
    """
    row = db.fetch_one(sql, {"project_id": project_id, "user_id": current_user["id"]})
    if not row:
        return False
    order = {"owner": 4, "editor": 3, "reviewer": 2, "viewer": 1}
    return order.get(row["project_role"], 0) >= order.get(min_role or "viewer", 0)


def get_project_id_by_document_id(document_id: int) -> int | None:
    sql = f"""
    SELECT project_id FROM {_schema}.document
    WHERE id = %(document_id)s
    """
    row = db.fetch_one(sql, {"document_id": document_id})
    return row["project_id"] if row else None


def get_project_id_by_version_id(version_id: int) -> int | None:
    sql = f"""
    SELECT d.project_id
    FROM {_schema}.document_version dv
    JOIN {_schema}.document d ON d.id = dv.document_id
    WHERE dv.id = %(version_id)s
    """
    row = db.fetch_one(sql, {"version_id": version_id})
    return row["project_id"] if row else None


def get_project_id_by_issue_id(issue_id: int) -> int | None:
    sql = f"""
    SELECT d.project_id
    FROM {_schema}.review_issue ri
    JOIN {_schema}.document_version dv ON dv.id = ri.version_id
    JOIN {_schema}.document d ON d.id = dv.document_id
    WHERE ri.id = %(issue_id)s
    """
    row = db.fetch_one(sql, {"issue_id": issue_id})
    return row["project_id"] if row else None


def get_project_id_by_run_id(run_id: int) -> int | None:
    sql = f"""
    SELECT d.project_id
    FROM {_schema}.review_run rr
    JOIN {_schema}.document_version dv ON dv.id = rr.version_id
    JOIN {_schema}.document d ON d.id = dv.document_id
    WHERE rr.id = %(run_id)s
    """
    row = db.fetch_one(sql, {"run_id": run_id})
    return row["project_id"] if row else None
