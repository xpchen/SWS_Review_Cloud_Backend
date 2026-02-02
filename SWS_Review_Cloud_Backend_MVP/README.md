(env) D:\Workspace\SWS_Review_Cloud_Backend\SWS_Review_Cloud_Backend_MVP>python -m celery -A app.worker.app worker --loglevel=info --pool=solo

# SWS Review Cloud Backend (MVP)

This is a minimal FastAPI backend to validate your **rule-review closed loop**:
- Left outline list: `/api/versions/{version_id}/outline`
- Right issues list: `/api/versions/{version_id}/issues`
- Center PDF preview URL: `/api/versions/{version_id}/pdf` (returns built-in `/static/demo.pdf` for now)

## 1) Requirements
- Python 3.11+
- PostgreSQL already prepared:
  - DB: `sws_review_cloud`
  - Schema: `sws`
  - Demo data inserted (your SQL script)

## 2) Install & Run (Windows)
```bash
cd sws-review-cloud-backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

## 3) Configure `.env`
- DATABASE_URL must point to your PostgreSQL
Example:
DATABASE_URL=postgresql://sws_app:YOUR_PASSWORD@localhost:5432/sws_review_cloud
BASE_URL=http://localhost:8000
DB_SCHEMA=sws

## 4) Quick Test
- Health: http://localhost:8000/health
- PDF url: http://localhost:8000/api/versions/1/pdf
- Outline: http://localhost:8000/api/versions/1/outline
- Issues: http://localhost:8000/api/versions/1/issues

> Replace `1` with the real `version_id` from your DB query.

## 5) Next Step
- Wire real PDF URL:
  - Local file streaming OR MinIO/OSS signed URL
- Add `POST /review-runs` to actually execute rule engine and write issues
- Add authentication/RBAC
