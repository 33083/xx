"""安全模块：密码哈希 + JWT 生成/校验。"""
import base64
import hashlib
from datetime import datetime, timedelta, timezone
from typing import Any

import bcrypt
import jwt
from jwt import PyJWTError

from app.config import settings
from app.schemas.auth import TokenData


# ---------------- 密码 ----------------
# bcrypt 限制 72 字节；超长密码先 sha256+base64 预哈希（固定 44 字节），
# 这样任意长度密码都能用，且不暴露原始长度。

def _prehash(pw: str) -> bytes:
    return base64.b64encode(hashlib.sha256(pw.encode("utf-8")).digest())


def hash_password(plain: str) -> str:
    return bcrypt.hashpw(_prehash(plain), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(_prehash(plain), hashed.encode("utf-8"))
    except (ValueError, TypeError):
        return False


# ---------------- JWT ----------------

def create_access_token(
    subject: str,
    user_id: int,
    role: str = "student",
    expires_delta: timedelta | None = None,
) -> str:
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    payload: dict[str, Any] = {
        "sub": subject,
        "user_id": user_id,
        "role": role,
        "exp": expire,
    }
    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def decode_access_token(token: str) -> TokenData | None:
    """解码并校验 JWT，返回 TokenData 或 None。"""
    credentials_exception_msg = "无法校验凭证"
    try:
        payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
        sub: str | None = payload.get("sub")
        user_id: int | None = payload.get("user_id")
        role: str = payload.get("role", "student")
        if sub is None or user_id is None:
            return None
        return TokenData(sub=sub, user_id=user_id, role=role)
    except PyJWTError:
        return None
