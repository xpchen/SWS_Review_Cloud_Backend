import logging
from .app import app
from .ai_review_tasks import _execute_ai_review

logger = logging.getLogger(__name__)

# 已停用：全部审查改为 AI 规则校验引擎。保留入口供测试/旧 pipeline 调用，实际执行 AI。
def _execute_rule_review(version_id: int, run_id: int, publish_events: bool = True):
    """原规则审查已停用，转调 AI 规则校验（publish_events 暂忽略）。"""
    logger.info(f"[版本 {version_id}] 规则审查已转调 AI 规则校验（旧 checkpoint 已停用）")
    _execute_ai_review(version_id, run_id)


@app.task(bind=True)
def run_rule_review_task(self, version_id: int, run_id: int):
    """Celery 任务：原规则审查已停用，统一转调 AI 规则校验。"""
    logger.info(f"[版本 {version_id}] run_rule_review_task 已转调 AI 规则校验（旧规则引擎已停用）")
    _execute_ai_review(version_id, run_id)
