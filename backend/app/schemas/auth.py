"""认证相关 schema。"""
from pydantic import BaseModel, EmailStr, Field


class LoginRequest(BaseModel):
    account: str = Field(..., description="用户名或邮箱")
    password: str = Field(..., min_length=6, max_length=64)


class RegisterRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=64, pattern=r"^[A-Za-z0-9_-]+$")
    email: EmailStr
    password: str = Field(..., min_length=6, max_length=64)
    nickname: str | None = Field(None, max_length=64)


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: int
    username: str
    role: str = "student"


class TokenData(BaseModel):
    """JWT 解析后的载荷。"""

    sub: str | None = None
    user_id: int | None = None
    role: str = "student"
