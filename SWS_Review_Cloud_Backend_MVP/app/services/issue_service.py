from .. import db
from ..settings import settings

_schema = settings.DB_SCHEMA


def get_issue(issue_id: int) -> dict | None:
    sql = f"""
    SELECT id, version_id, run_id, issue_type, severity, title, description, suggestion,
           confidence, status, page_no, evidence_block_ids, evidence_quotes, anchor_rects, created_at, updated_at
    FROM {_schema}.review_issue
    WHERE id = %(issue_id)s
    """
    return db.fetch_one(sql, {"issue_id": issue_id})


def apply_action(issue_id: int, action: str, actor_user_id: int, action_reason: str | None = None) -> bool:
    status_map = {"ACCEPT": "ACCEPTED", "IGNORE": "IGNORED", "FIX": "FIXED", "COMMENT": None}
    new_status = status_map.get(action)
    if new_status is None and action != "COMMENT":
        return False
    sql_log = f"""
    INSERT INTO {_schema}.issue_action_log (issue_id, action, action_reason, actor_user_id)
    VALUES (%(issue_id)s, %(action)s, %(action_reason)s, %(actor_user_id)s)
    """
    db.execute(sql_log, {
        "issue_id": issue_id, "action": action, "action_reason": action_reason, "actor_user_id": actor_user_id,
    })
    if new_status:
        sql_up = f"""
        UPDATE {_schema}.review_issue SET status = %(status)s, updated_at = now() WHERE id = %(issue_id)s
        """
        db.execute(sql_up, {"issue_id": issue_id, "status": new_status})
    return True
