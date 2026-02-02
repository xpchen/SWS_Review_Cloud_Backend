from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from ..models.projects import ProjectCreate
from ..models.common import ok_data
from ..services import project_service
from ..core.deps import get_current_user, require_project_member

router = APIRouter(prefix="/api", tags=["projects"])


@router.post("/projects", response_model=dict)
def create_project(body: ProjectCreate, current_user: Annotated[dict, Depends(get_current_user)]):
    pid = project_service.create_project(body.name, current_user["id"], body.location)
    proj = project_service.get_project(pid)
    return ok_data(proj)


@router.get("/projects", response_model=dict)
def list_projects(current_user: Annotated[dict, Depends(get_current_user)]):
    rows = project_service.list_projects(current_user["id"])
    return ok_data(rows)


@router.get("/projects/{project_id}", response_model=dict)
def get_project(project_id: int, current_user: Annotated[dict, Depends(get_current_user)]):
    if not require_project_member(project_id, current_user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not a project member")
    proj = project_service.get_project(project_id)
    if not proj:
        raise HTTPException(status_code=404, detail="Project not found")
    return ok_data(proj)
