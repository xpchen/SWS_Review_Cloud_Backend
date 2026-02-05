import json
import asyncio
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse

from ..models.common import ok_data
from ..models.review import ReviewRunCreate
from ..services.review_run_service import create_review_run, get_review_run
from ..core.deps import get_current_user, require_project_member, get_project_id_by_run_id
from ..worker.ai_review_tasks import run_ai_review_task

router = APIRouter(prefix="/api", tags=["review-runs"])


@router.post("/versions/{version_id}/review-runs", response_model=dict)
def create_run(
    version_id: int,
    body: ReviewRunCreate,
    current_user: Annotated[dict, Depends(get_current_user)],
):
    from ..core.deps import get_project_id_by_version_id
    project_id = get_project_id_by_version_id(version_id)
    if project_id is None:
        raise HTTPException(status_code=404, detail="Version not found")
    if not require_project_member(project_id, current_user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not a project member")
    # 当前全部使用 AI 规则校验引擎，不再执行旧规则引擎
    run_id = create_review_run(version_id, "AI")
    run_ai_review_task.delay(version_id, run_id)
    run = get_review_run(run_id)
    return ok_data(run)


@router.get("/review-runs/{run_id}", response_model=dict)
def get_run(run_id: int, current_user: Annotated[dict, Depends(get_current_user)]):
    project_id = get_project_id_by_run_id(run_id)
    if project_id is None:
        raise HTTPException(status_code=404, detail="Run not found")
    if not require_project_member(project_id, current_user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not a project member")
    run = get_review_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    return ok_data(run)


@router.get("/review-runs/{run_id}/events")
async def run_events(run_id: int, current_user: Annotated[dict, Depends(get_current_user)]):
    project_id = get_project_id_by_run_id(run_id)
    if project_id is None:
        raise HTTPException(status_code=404, detail="Run not found")
    if not require_project_member(project_id, current_user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not a project member")

    async def event_generator():
        while True:
            run = get_review_run(run_id)
            if not run:
                break
            payload = {"run_id": run_id, "progress": run.get("progress", 0), "message": run.get("status", "")}
            yield f"event: run_progress\ndata: {json.dumps(payload, default=str)}\n\n"
            if run.get("status") in ("DONE", "FAILED", "CANCELED"):
                yield f"event: run_done\ndata: {json.dumps({'run_id': run_id}, default=str)}\n\n"
                break
            await asyncio.sleep(1)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
