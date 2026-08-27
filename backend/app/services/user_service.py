"""用户业务：注册、登录、查询。"""
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.security import hash_password, verify_password
from app.models.user import User
from app.schemas.auth import LoginRequest, RegisterRequest


def get_user_by_username(db: Session, username: str) -> User | None:
    return db.scalar(select(User).where(User.username == username))


def get_user_by_email(db: Session, email: str) -> User | None:
    return db.scalar(select(User).where(User.email == email))


def get_user_by_account(db: Session, account: str) -> User | None:
    """按用户名或邮箱查询。"""
    return db.scalar(
        select(User).where((User.username == account) | (User.email == account))
    )


def register_user(db: Session, payload: RegisterRequest) -> User:
    existing = get_user_by_username(db, payload.username) or get_user_by_email(
        db, payload.email
    )
    if existing:
        raise ValueError("用户名或邮箱已被注册")
    user = User(
        username=payload.username,
        email=payload.email,
        hashed_password=hash_password(payload.password),
        nickname=payload.nickname or payload.username,
        role="student",
    )
    db.add(user)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise ValueError("用户名或邮箱已被注册")
    db.refresh(user)
    return user


def authenticate(db: Session, payload: LoginRequest) -> User:
    user = get_user_by_account(db, payload.account)
    if not user or not verify_password(payload.password, user.hashed_password):
        raise ValueError("账号或密码错误")
    if not user.is_active:
        raise ValueError("账号已被禁用")
    return user
