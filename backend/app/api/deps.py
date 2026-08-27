"""FastAPI 公共依赖：JWT 鉴权、当前用户、管理员校验。"""
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.core.security import decode_access_token
from app.models.user import User

oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl=f"{settings.API_V1_PREFIX}/auth/login", auto_error=False
)


def get_current_user(
    token: str | None = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> User:
    """从 JWT 解析当前登录用户。"""
    creds_exc = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="未登录或凭证已过期",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if not token:
        raise creds_exc
    token_data = decode_access_token(token)
    if token_data is None or token_data.user_id is None:
        raise creds_exc
    user = db.get(User, token_data.user_id)
    if user is None or not user.is_active:
        raise creds_exc
    return user


def get_current_admin(user: User = Depends(get_current_user)) -> User:
    """要求当前用户是管理员。"""
    if user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="需要管理员权限")
    return user
