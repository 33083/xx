"""对话记录模型：会话 + 多轮消息。

LangChain 的 Memory 由对话历史持久化。
"""
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base, BigInt


class Conversation(Base):
    __tablename__ = "conversations"

    id: Mapped[int] = mapped_column(BigInt, primary_key=True, autoincrement=True)
    owner_id: Mapped[int] = mapped_column(
        BigInt, ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    title: Mapped[str] = mapped_column(String(255), default="新对话", comment="会话标题")
    skill: Mapped[str | None] = mapped_column(
        String(64), nullable=True, comment="关联技能: review/resume/lab"
    )
    agent_type: Mapped[str] = mapped_column(
        String(32), default="chat", comment="agent 类型: chat/react/rag"
    )
    message_count: Mapped[int] = mapped_column(Integer, default=0, comment="消息数")

    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    def __repr__(self) -> str:
        return f"<Conversation id={self.id} title={self.title!r}>"


class ConversationMessage(Base):
    __tablename__ = "conversation_messages"

    id: Mapped[int] = mapped_column(BigInt, primary_key=True, autoincrement=True)
    conversation_id: Mapped[int] = mapped_column(
        BigInt, ForeignKey("conversations.id", ondelete="CASCADE"), index=True
    )
    role: Mapped[str] = mapped_column(String(16), comment="user/assistant/system/tool")
    content: Mapped[str] = mapped_column(Text, comment="消息内容")
    # 多模态：用户消息附带的图片 URL（base64 data url 或后端静态文件 URL）
    image_url: Mapped[str | None] = mapped_column(String(1024), nullable=True, comment="用户消息附带的图片URL")
    # 关联的工具调用 / 引用的文档，JSON 字符串
    tool_calls: Mapped[str | None] = mapped_column(Text, nullable=True)
    refs: Mapped[str | None] = mapped_column(Text, nullable=True, comment="引用文档片段")

    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    def __repr__(self) -> str:
        return f"<Message id={self.id} role={self.role!r}>"
