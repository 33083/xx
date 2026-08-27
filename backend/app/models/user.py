"""用户模型。"""
from datetime import datetime

from sqlalchemy import DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base, BigInt


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(BigInt, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, index=True, comment="用户名")
    email: Mapped[str] = mapped_column(String(128), unique=True, index=True, comment="邮箱")
    hashed_password: Mapped[str] = mapped_column(String(255), comment="密码哈希")
    nickname: Mapped[str | None] = mapped_column(String(64), nullable=True, comment="昵称")
    avatar: Mapped[str | None] = mapped_column(String(255), nullable=True, comment="头像 URL")
    role: Mapped[str] = mapped_column(String(16), default="student", comment="角色: student/admin")
    is_active: Mapped[bool] = mapped_column(default=True, comment="是否启用")

    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    def __repr__(self) -> str:
        return f"<User id={self.id} username={self.username!r}>"
