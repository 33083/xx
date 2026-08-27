"""用户接口：查看 / 更新个人资料。后续可扩管理后台。"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from sqlalchemy import func

from app.api.deps import get_current_admin, get_current_user
from app.database import get_db
from app.models.conversation import Conversation, ConversationMessage
from app.models.document import Document
from app.models.user import User
from app.schemas.common import ApiResponse
from app.schemas.user import AdminStats, UserActiveUpdate, UserOut, UserUpdate

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/me", response_model=ApiResponse[UserOut])
def get_me(current: User = Depends(get_current_user)):
    return ApiResponse(data=UserOut.model_validate(current))


@router.patch("/me", response_model=ApiResponse[UserOut])
def update_me(
    payload: UserUpdate,
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if payload.email and payload.email != current.email:
        exists = db.scalar(select(User).where(User.email == payload.email))
        if exists:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="邮箱已被占用")
    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(current, k, v)
    db.commit()
    db.refresh(current)
    return ApiResponse(data=UserOut.model_validate(current))


@router.get("", response_model=ApiResponse[list[UserOut]])
def list_users(
    _: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """管理员：列出全部用户。"""
    users = db.scalars(select(User).order_by(User.id.desc())).all()
    return ApiResponse(data=[UserOut.model_validate(u) for u in users])


@router.get("/stats", response_model=ApiResponse[AdminStats])
def admin_stats(
    _: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """管理员：系统概览统计。"""
    users_total = db.scalar(select(func.count()).select_from(User)) or 0
    active = (
        db.scalar(select(func.count()).select_from(User).where(User.is_active.is_(True))) or 0
    )
    admins = db.scalar(select(func.count()).select_from(User).where(User.role == "admin")) or 0
    docs = db.scalar(select(func.count()).select_from(Document)) or 0
    convs = db.scalar(select(func.count()).select_from(Conversation)) or 0
    msgs = db.scalar(select(func.count()).select_from(ConversationMessage)) or 0
    shared_chunks = 0
    try:
        from app.core.vectorstore import shared_collection
        shared_chunks = int(shared_collection.count() or 0)
    except Exception:
        shared_chunks = 0
    return ApiResponse(
        data=AdminStats(
            users=users_total,
            active_users=active,
            admins=admins,
            documents=docs,
            conversations=convs,
            messages=msgs,
            shared_chunks=shared_chunks,
        )
    )


@router.patch("/{uid}/active", response_model=ApiResponse[UserOut])
def set_user_active(
    uid: int,
    payload: UserActiveUpdate,
    _: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """管理员：启用/禁用用户。"""
    user = db.get(User, uid)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="用户不存在")
    user.is_active = payload.is_active
    db.commit()
    db.refresh(user)
    return ApiResponse(data=UserOut.model_validate(user))


@router.delete("/{uid}", response_model=ApiResponse[dict])
def delete_user(
    uid: int,
    current: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """管理员：删除用户（级联删除其文档/会话）。"""
    if uid == current.id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="不能删除自己")
    user = db.get(User, uid)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="用户不存在")
    db.delete(user)
    db.commit()
    return ApiResponse(data={"deleted": True})
