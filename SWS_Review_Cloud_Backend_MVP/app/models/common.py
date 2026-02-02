from typing import Any, Generic, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


class OkResponse(BaseModel, Generic[T]):
    code: str = "OK"
    message: str = "success"
    data: T | None = None


def ok_data(data: Any):
    return {"code": "OK", "message": "success", "data": data}
