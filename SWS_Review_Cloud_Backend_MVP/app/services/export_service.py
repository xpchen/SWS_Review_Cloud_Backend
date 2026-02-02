import io
from .. import db
from ..settings import settings
from ..core.deps import get_project_id_by_version_id

_schema = settings.DB_SCHEMA


def get_issues_for_export(version_id: int, status: str | None = None, severity: str | None = None) -> list[dict]:
    where = ["version_id = %(version_id)s"]
    params = {"version_id": version_id}
    if status:
        where.append("status = %(status)s")
        params["status"] = status
    if severity:
        where.append("severity = %(severity)s")
        params["severity"] = severity
    sql = f"""
    SELECT id, issue_type, severity, title, description, suggestion, confidence, status, page_no, created_at
    FROM {_schema}.review_issue
    WHERE {' AND '.join(where)}
    ORDER BY id DESC
    """
    return db.fetch_all(sql, params)


def build_issues_xlsx(version_id: int, status: str | None = None, severity: str | None = None) -> bytes:
    import openpyxl
    from openpyxl.styles import Font, Alignment
    rows = get_issues_for_export(version_id, status, severity)
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "审查问题"
    headers = ["ID", "类型", "严重程度", "标题", "描述", "建议", "置信度", "状态", "页码", "创建时间"]
    for col, h in enumerate(headers, 1):
        ws.cell(row=1, column=col, value=h)
        ws.cell(row=1, column=col).font = Font(bold=True)
    for row_idx, r in enumerate(rows, 2):
        ws.cell(row=row_idx, column=1, value=r.get("id"))
        ws.cell(row=row_idx, column=2, value=r.get("issue_type"))
        ws.cell(row=row_idx, column=3, value=r.get("severity"))
        ws.cell(row=row_idx, column=4, value=r.get("title"))
        ws.cell(row=row_idx, column=5, value=r.get("description"))
        ws.cell(row=row_idx, column=6, value=r.get("suggestion"))
        ws.cell(row=row_idx, column=7, value=r.get("confidence"))
        ws.cell(row=row_idx, column=8, value=r.get("status"))
        ws.cell(row=row_idx, column=9, value=r.get("page_no"))
        ws.cell(row=row_idx, column=10, value=str(r.get("created_at")) if r.get("created_at") else "")
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()

