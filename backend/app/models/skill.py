"""技能模型：可插拔技能注册表。

技能本身在 Python 代码中通过装饰器注册，数据库表只存"启用/禁用"状态和配置。
"""
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base, BigInt


class Skill(Base):
    __tablename__ = "skills"

    id: Mapped[int] = mapped_column(BigInt, primary_key=True, autoincrement=True)
    skill_key: Mapped[str] = mapped_column(String(64), index=True, comment="技能唯一键")
    name: Mapped[str] = mapped_column(String(128), comment="展示名")
    description: Mapped[str | None] = mapped_column(Text, nullable=True, comment="描述")
    category: Mapped[str] = mapped_column(
        String(32), default="general", comment="分类: review/resume/lab/tool"
    )
    enabled: Mapped[bool] = mapped_column(default=True, comment="是否启用")
    config_json: Mapped[str | None] = mapped_column(Text, nullable=True, comment="JSON 配置")
    # 启用它的用户可单独覆盖全局配置，这里先留扩展位
    owner_id: Mapped[int | None] = mapped_column(
        BigInt, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    def __repr__(self) -> str:
        return f"<Skill key={self.skill_key!r} enabled={self.enabled}>"
