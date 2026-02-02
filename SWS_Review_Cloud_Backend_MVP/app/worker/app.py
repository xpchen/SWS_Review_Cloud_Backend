import sys
from celery import Celery
from ..settings import settings

app = Celery(
    "sws_worker",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.REDIS_URL,
    include=["app.worker.tasks", "app.worker.review_tasks", "app.worker.kb_tasks", "app.worker.ai_review_tasks"],
)
app.conf.task_serializer = "json"
app.conf.result_serializer = "json"
app.conf.accept_content = ["json"]
app.conf.timezone = "UTC"
app.conf.enable_utc = True

# Windows 上使用 solo 池（prefork 在 Windows 上有权限问题）
if sys.platform == "win32":
    app.conf.worker_pool = "solo"
    # 或者使用 threads 池（如果需要并发）
    # app.conf.worker_pool = "threads"
    # app.conf.worker_threads = 4
