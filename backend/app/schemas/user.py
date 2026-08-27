"""用户相关 schema。"""
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class UserOut(BaseModel):
    """对外输出的用户信息（不含密码）。"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    email: EmailStr
    nickname: str | None = None
    avatar: str | None = None
    role: str = "student"
    is_active: bool = True
    created_at: datetime


class UserUpdate(BaseModel):
    nickname: str | None = Field(None, max_length=64)
    avatar: str | None = Field(None, max_length=255)
    email: EmailStr | None = None


class UserActiveUpdate(BaseModel):
    """管理员：启用/禁用用户。"""

    is_active: bool


class AdminStats(BaseModel):
    """管理员：系统概览统计。"""

    users: int = 0
    active_users: int = 0
    admins: int = 0
    documents: int = 0
    conversations: int = 0
    messages: int = 0
    shared_chunks: int = 0
