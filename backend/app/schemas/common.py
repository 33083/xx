"""通用响应封装。"""
from typing import Generic, List, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class ApiResponse(BaseModel, Generic[T]):
    """统一响应格式::

        {"code": 0, "msg": "ok", "data": ...}
    """

    code: int = 0
    msg: str = "ok"
    data: T | None = None


class PageResponse(BaseModel, Generic[T]):
    """分页响应。"""

    total: int = 0
    page: int = 1
    page_size: int = Field(20, alias="pageSize")
    items: List[T] = []
