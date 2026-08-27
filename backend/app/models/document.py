"""文档模型：用户上传的学习资料 / 面经 / 简历。

用于 RAG 检索的文档元信息。向量本身存到 Chroma，业务元数据存这里。
"""
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base, BigInt


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[int] = mapped_column(BigInt, primary_key=True, autoincrement=True)
    owner_id: Mapped[int] = mapped_column(
        BigInt, ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    title: Mapped[str] = mapped_column(String(255), comment="文档标题")
    file_type: Mapped[str] = mapped_column(String(32), comment="文件类型: pdf/txt/md/image")
    file_path: Mapped[str] = mapped_column(String(512), comment="存储路径")
    file_size: Mapped[int] = mapped_column(Integer, default=0, comment="字节数")
    md5: Mapped[str | None] = mapped_column(
        String(64), nullable=True, index=True, comment="文件内容 MD5（去重用）"
    )
    category: Mapped[str] = mapped_column(
        String(32), default="material", comment="分类: material/resume/interview"
    )
    # Chroma 集合中的文档 id 列表（切片后会有多个）
    chroma_collection: Mapped[str | None] = mapped_column(String(128), nullable=True)
    chunk_count: Mapped[int] = mapped_column(Integer, default=0, comment="切片数量")
    description: Mapped[str | None] = mapped_column(Text, nullable=True, comment="备注")

    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    def __repr__(self) -> str:
        return f"<Document id={self.id} title={self.title!r}>"
