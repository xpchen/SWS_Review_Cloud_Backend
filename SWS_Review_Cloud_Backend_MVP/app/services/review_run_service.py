from .. import db
from ..settings import settings

_schema = settings.DB_SCHEMA


def create_review_run(version_id: int, run_type: str) -> int:
    sql = f"""
    INSERT INTO {_schema}.review_run (version_id, run_type, status, progress)
    VALUES (%(version_id)s, %(run_type)s, 'PENDING', 0)
    RETURNING id
    """
    with db.pool.connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, {"version_id": version_id, "run_type": run_type})
            return cur.fetchone()[0]


def get_review_run(run_id: int) -> dict | None:
    sql = f"""
    SELECT id, version_id, run_type, status, progress, started_at, finished_at, error_message, created_at
    FROM {_schema}.review_run
    WHERE id = %(run_id)s
    """
    return db.fetch_one(sql, {"run_id": run_id})


def update_run_status(run_id: int, status: str, progress: int | None = None, error_message: str | None = None) -> None:
    parts = ["status = %(status)s", "updated_at = now()"]
    params = {"run_id": run_id, "status": status}
    if progress is not None:
        parts.append("progress = %(progress)s")
        params["progress"] = progress
    if error_message is not None:
        parts.append("error_message = %(error_message)s")
        params["error_message"] = error_message
    if status == "RUNNING":
        parts.append("started_at = COALESCE(started_at, now())")
    elif status in ("DONE", "FAILED", "CANCELED"):
        parts.append("finished_at = now()")
    sql = f"UPDATE {_schema}.review_run SET {', '.join(parts)} WHERE id = %(run_id)s"
    db.execute(sql, params)


def insert_issue(
    version_id: int,
    run_id: int | None,
    issue_type: str,
    severity: str,
    title: str,
    description: str,
    suggestion: str,
    confidence: float,
    page_no: int | None = None,
    evidence_block_ids: list | None = None,
    evidence_quotes: list | None = None,
    anchor_rects: list | None = None,
    checkpoint_code: str | None = None,
    review_type: str | None = None,
) -> int:
    import json
    from .block_service import get_block_page_info

    # 如果page_no未提供，从evidence_block_ids的第一个block的anchor反查
    if page_no is None and evidence_block_ids:
        page_info = get_block_page_info(evidence_block_ids[:1])
        if page_info and evidence_block_ids[0] in page_info:
            page_no = page_info[evidence_block_ids[0]]["page_no"]
            # 如果anchor_rects也未提供，从anchor获取
            if anchor_rects is None:
                anchor_rects = page_info[evidence_block_ids[0]].get("anchor_rects")

    # 如果还是没有page_no，默认设为1（向后兼容）
    if page_no is None:
        page_no = 1

    # 基础字段（不含 review_type）；review_type 可选，若表中无该列则自动降级
    fields_base = [
        "version_id", "run_id", "issue_type", "severity", "title", "description",
        "suggestion", "confidence", "status", "page_no",
        "evidence_block_ids", "evidence_quotes", "anchor_rects", "checkpoint_code",
    ]
    values_base = [
        "%(version_id)s", "%(run_id)s", "%(issue_type)s", "%(severity)s",
        "%(title)s", "%(description)s", "%(suggestion)s", "%(confidence)s",
        "'NEW'", "%(page_no)s",
        "%(evidence_block_ids)s", "%(evidence_quotes)s", "%(anchor_rects)s", "%(checkpoint_code)s",
    ]
    params = {
        "version_id": version_id, "run_id": run_id, "issue_type": issue_type,
        "severity": severity, "title": title, "description": description,
        "suggestion": suggestion, "confidence": confidence, "page_no": page_no,
        "evidence_block_ids": json.dumps(evidence_block_ids or []),
        "evidence_quotes": json.dumps(evidence_quotes or []),
        "anchor_rects": json.dumps(anchor_rects or []),
        "checkpoint_code": checkpoint_code,
    }

    with db.pool.connection() as conn:
        with conn.cursor() as cur:
            # 若传入 review_type，先尝试带 review_type 插入；列不存在或无权限时降级为不含 review_type
            if review_type is not None:
                fields = fields_base + ["review_type"]
                values = values_base + ["%(review_type)s"]
                params_with_rt = {**params, "review_type": review_type}
                sql_with_rt = f"""
                INSERT INTO {_schema}.review_issue ({', '.join(fields)})
                VALUES ({', '.join(values)})
                RETURNING id
                """
                try:
                    cur.execute(sql_with_rt, params_with_rt)
                    return cur.fetchone()[0]
                except Exception as e:
                    err = str(e).lower()
                    if "review_type" in err or "column" in err or "属主" in err or "owner" in err or "permission" in err:
                        pass  # 降级：不带 review_type 再插一次
                    else:
                        raise
            sql = f"""
            INSERT INTO {_schema}.review_issue ({', '.join(fields_base)})
            VALUES ({', '.join(values_base)})
            RETURNING id
            """
            cur.execute(sql, params)
            return cur.fetchone()[0]
