from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from ..models.auth import LoginRequest
from ..models.common import ok_data
from ..services import auth_service
from ..core.deps import get_current_user

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/login", response_model=dict)
def login(body: LoginRequest):
    user = auth_service.login(body.username, body.password)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid username or password")
    tokens = auth_service.create_tokens(user["id"])
    return ok_data({"access_token": tokens["access_token"], "refresh_token": tokens["refresh_token"], "token_type": "bearer"})


@router.get("/me", response_model=dict)
def me(current_user: Annotated[dict, Depends(get_current_user)]):
    return ok_data({"id": current_user["id"], "username": current_user["username"], "display_name": current_user.get("display_name")})
