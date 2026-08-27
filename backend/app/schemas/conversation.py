"""对话模块 schema。"""
from datetime import datetime
from enum import Enum
from typing import Any, List, Optional

from pydantic import BaseModel, ConfigDict, Field


class AgentType(str, Enum):
    CHAT = "chat"
    RAG = "rag"
    REACT = "react"


class ConversationCreate(BaseModel):
    title: Optional[str] = None
    skill: Optional[str] = None
    agent_type: AgentType = AgentType.RAG


class ConversationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    title: str
    skill: Optional[str] = None
    agent_type: str
    message_count: int = 0
    updated_at: datetime


class ConversationTitleUpdate(BaseModel):
    title: str = Field(..., min_length=1, max_length=120)


class MessageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: Optional[int] = None
    role: str
    content: str
    image_url: Optional[str] = None
    refs: Optional[Any] = None
    created_at: Optional[datetime] = None


class ChatRequest(BaseModel):
    conversation_id: Optional[int] = None
    message: str = Field(..., min_length=1, max_length=8000)
    image_url: Optional[str] = Field(None, max_length=2048, description="多模态：用户附带的图片URL")
    use_rag: bool = True
    use_web_search: bool = Field(False, description="强制启用联网搜索（博查 AI），忽略 LLM 自动判断")
    rag_category: str = Field("all", description="RAG 检索分类：all/material/resume/interview")
    agent_type: AgentType = AgentType.RAG
    skill: Optional[str] = None


class ChatResponse(BaseModel):
    conversation_id: int
    message_id: int
    answer: str
    refs: List[Any] = []
    rag_ok: bool = True


class SearchHit(BaseModel):
    """会话全文搜索命中项。type: conversation(标题命中) / message(内容命中)。"""

    type: str = "message"
    conversation_id: int
    title: str = ""
    snippet: str = ""
    role: str = "message"
    created_at: str = ""
