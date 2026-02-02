from pydantic import BaseModel


class ProjectCreate(BaseModel):
    name: str
    location: str | None = None


class ProjectOut(BaseModel):
    id: int
    name: str
    location: str | None
    owner_user_id: int
