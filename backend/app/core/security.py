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


# ---------------- JWT 黑名单 ----------------

def _get_blacklist_redis():
    """获取 Redis 客户端用于黑名单（连接失败返回 None）。"""
    try:
        import redis as redis_lib
        rdb = redis_lib.Redis.from_url(
            settings.redis_url,
            socket_connect_timeout=1.5,
            socket_timeout=2.0,
            decode_responses=True,
        )
        rdb.ping()
        return rdb
    except Exception:
        return None


def blacklist_token(token: str) -> None:
    """将 token 加入黑名单（退出登录时调用）。"""
    if not settings.JWT_BLACKLIST_ENABLED:
        return
    rdb = _get_blacklist_redis()
    if rdb is None:
        return
    try:
        # 解析 token 的过期时间，设置相同的 TTL
        payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
        exp = payload.get("exp")
        if exp:
            import time
            ttl = max(1, int(exp) - int(time.time()))
        else:
            ttl = settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
        rdb.setex(f"jwt_blacklist:{token}", ttl, "1")
    except Exception:
        pass


def is_token_blacklisted(token: str) -> bool:
    """检查 token 是否在黑名单中。"""
    if not settings.JWT_BLACKLIST_ENABLED:
        return False
    rdb = _get_blacklist_redis()
    if rdb is None:
        return False  # Redis 不可用时放行，避免锁死用户
    try:
        return rdb.exists(f"jwt_blacklist:{token}") > 0
    except Exception:
        return False
