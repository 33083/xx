"""文档模块 schema。"""
from datetime import datetime
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field


class DocCategory(str, Enum):
    MATERIAL = "material"
    RESUME = "resume"
    INTERVIEW = "interview"


class DocumentUploaded(BaseModel):
    id: int
    title: str
    chunk_count: int
    category: str


class DocumentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    title: str
    file_type: str
    category: str
    file_size: int = 0
    chunk_count: int = 0
    description: Optional[str] = None
    created_at: datetime


class DocumentListOut(BaseModel):
    items: List[DocumentOut]
    total: int
    page: int
    page_size: int


class DocumentUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = Field(None, max_length=5000)


class DocumentPreviewOut(BaseModel):
    doc_id: int
    title: str
    file_type: str
    category: str
    preview_url: Optional[str] = None  # PDF 用（浏览器内嵌预览）
    text: Optional[str] = None  # 其余类型提取的纯文本


class DocDeleteOut(BaseModel):
    deleted: bool


class ChunkRef(BaseModel):
    doc_id: int = 0
    doc_title: str = ""
    chunk_index: int = 0
    content: str = ""
    score: float = 0.0
    source: str = "user"  # 片段来源：user=个人文档库 / shared=公共知识库


class RagSearchOut(BaseModel):
    query: str
    hits: List[ChunkRef] = []
    rag_ok: bool = True  # 检索链路是否正常（Chroma 可达）


class RagSearchIn(BaseModel):
    query: str
    top_k: Optional[int] = None
