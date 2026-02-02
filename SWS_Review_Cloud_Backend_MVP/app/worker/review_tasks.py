import json
import redis
from ..settings import settings
from ..rule_engine import EXECUTOR_REGISTRY
from ..services.review_run_service import (
    get_review_run,
    update_run_status,
    insert_issue,
)
from ..services.checkpoint_runner import build_context, run_checkpoints
from .app import app

_redis = redis.from_url(settings.REDIS_URL)
CHANNEL_PREFIX = "review_run:"


def _publish(run_id: int, event: str, data: dict) -> None:
    payload = {"event": event, "run_id": run_id, **data}
    _redis.publish(f"{CHANNEL_PREFIX}{run_id}", json.dumps(payload, default=str))


def _execute_rule_review(version_id: int, run_id: int, publish_events: bool = True):
    """
    执行规则审查的核心逻辑（不依赖Celery装饰器）
    
    Args:
        version_id: 版本ID
        run_id: 审查运行ID
        publish_events: 是否发布Redis事件（默认True，直接执行时可设为False）
    """
    run = get_review_run(run_id)
    if not run or run["version_id"] != version_id:
        return
    update_run_status(run_id, "RUNNING", progress=0)
    if publish_events:
        _publish(run_id, "run_progress", {"progress": 0, "message": "规则校验开始"})
    
    # 构建执行上下文
    context = build_context(version_id)
    
    # 执行RULE类型的checkpoint
    drafts_with_checkpoint = run_checkpoints(context, "RULE", EXECUTOR_REGISTRY)
    total = len(drafts_with_checkpoint)
    for i, (d, checkpoint_code) in enumerate(drafts_with_checkpoint):
        issue_id = insert_issue(
            version_id=version_id,
            run_id=run_id,
            issue_type=d.issue_type,
            severity=d.severity,
            title=d.title,
            description=d.description,
            suggestion=d.suggestion,
            confidence=d.confidence,
            page_no=d.page_no,
            evidence_block_ids=d.evidence_block_ids,
            evidence_quotes=d.evidence_quotes,
            anchor_rects=d.anchor_rects,
            checkpoint_code=checkpoint_code,
        )
        if publish_events:
            _publish(run_id, "issue_created", {"issue_id": issue_id, "title": d.title, "page_no": d.page_no, "severity": d.severity})
        progress = int((i + 1) / total * 100) if total else 100
        update_run_status(run_id, "RUNNING", progress=progress)
        if publish_events:
            _publish(run_id, "run_progress", {"progress": progress, "message": f"已发现 {i + 1} 条问题"})
    update_run_status(run_id, "DONE", progress=100)
    if publish_events:
        _publish(run_id, "run_done", {})


@app.task(bind=True)
def run_rule_review_task(self, version_id: int, run_id: int):
    """Celery任务包装器"""
    _execute_rule_review(version_id, run_id, publish_events=True)
