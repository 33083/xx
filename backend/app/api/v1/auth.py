"""认证接口：注册、登录、获取当前用户。"""
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.ratelimit import LIMITER, client_ip, rate_limit_ip
from app.core.security import create_access_token
from app.database import get_db
from app.models.user import User
from app.schemas.auth import LoginRequest, RegisterRequest, Token
from app.schemas.user import UserOut
from app.services import user_service

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=Token, status_code=status.HTTP_201_CREATED)
def register(
    payload: RegisterRequest,
    db: Session = Depends(get_db),
    _rate: None = Depends(rate_limit_ip(10, 600)),  # 同一 IP 10 次/10 分钟，防恶意注册
):
    from app.core.sensitive import check_sensitive

    bad = check_sensitive(payload.username) or check_sensitive(payload.nickname or "")
    if bad:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"包含敏感词：{bad}")
    try:
        user = user_service.register_user(db, payload)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    token = create_access_token(user.username, user.id, user.role)
    return Token(
        access_token=token, user_id=user.id, username=user.username, role=user.role
    )


@router.post("/login", response_model=Token)
def login(
    payload: LoginRequest,
    request: Request,
    db: Session = Depends(get_db),
    _rate: None = Depends(rate_limit_ip(30, 60)),
):
    # 登录防爆破：账号维度 5 次/10 分钟、IP 维度 20 次/10 分钟，超限临时锁定
    acct_key = f"login_fail:{payload.account.strip().lower()}"
    ip_key = f"login_ip:{client_ip(request)}"
    if LIMITER.over_limit(acct_key, 5, 600) or LIMITER.over_limit(ip_key, 20, 600):
        raise HTTPException(status_code=429, detail="尝试次数过多，请 10 分钟后再试")
    try:
        user = user_service.authenticate(db, payload)
    except ValueError as e:
        LIMITER.allow(acct_key, 5, 600)
        LIMITER.allow(ip_key, 20, 600)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(e))
    LIMITER.reset(acct_key)
    token = create_access_token(user.username, user.id, user.role)
    return Token(
        access_token=token, user_id=user.id, username=user.username, role=user.role
    )


# 兼容 OAuth2PasswordRequestForm（Swagger UI 的 Authorize 按钮）
@router.post("/login/form", response_model=Token, include_in_schema=False)
def login_form(
    form: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
    _rate: None = Depends(rate_limit_ip(30, 60)),
):
    payload = LoginRequest(account=form.username, password=form.password)
    try:
        user = user_service.authenticate(db, payload)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(e))
    token = create_access_token(user.username, user.id, user.role)
    return Token(
        access_token=token, user_id=user.id, username=user.username, role=user.role
    )


@router.get("/me", response_model=UserOut)
def me(current: User = Depends(get_current_user)):
    return current
