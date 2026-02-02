from .. import db
from ..core.security import verify_password, create_access_token, create_refresh_token, decode_token
from ..settings import settings

_schema = settings.DB_SCHEMA


def get_user_by_username(username: str) -> dict | None:
    sql = f"""
    SELECT id, username, password_hash, display_name, status
    FROM {_schema}.sys_user
    WHERE username = %(username)s
    """
    return db.fetch_one(sql, {"username": username})


def login(username: str, password: str) -> dict | None:
    user = get_user_by_username(username)
    if not user or user.get("status") != "active":
        return None
    if not verify_password(password, user["password_hash"]):
        return None
    return {
        "id": user["id"],
        "username": user["username"],
        "display_name": user.get("display_name"),
    }


def create_tokens(user_id: int) -> dict:
    return {
        "access_token": create_access_token(user_id),
        "refresh_token": create_refresh_token(user_id),
        "token_type": "bearer",
    }
