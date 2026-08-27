"""对话模块路由：会话 CRUD + 同步聊天 + SSE 流式聊天。"""
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.database import get_db
from app.models.user import User
from app.schemas.common import ApiResponse
from app.schemas.conversation import (
    ChatRequest,
    ChatResponse,
    ConversationCreate,
    ConversationOut,
    ConversationTitleUpdate,
    MessageOut,
    SearchHit,
)
from app.schemas.document import RagSearchIn, RagSearchOut
from app.services import chat_service
from app.services.rag_service import rag_search

router = APIRouter(prefix="/conversations", tags=["conversations"])


# -------------- 会话 --------------

@router.post("", response_model=ApiResponse[ConversationOut])
def new_conversation(
    payload: ConversationCreate,
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return ApiResponse(data=chat_service.create_conversation(current, payload, db))


@router.get("", response_model=ApiResponse[list[ConversationOut]])
def list_my_conversations(
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return ApiResponse(data=chat_service.list_conversations(current, db))


@router.get("/search", response_model=ApiResponse[list[SearchHit]])
def search_conversations(
    q: str = "",
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """全文搜索：按关键词匹配会话标题 / 消息内容。"""
    return ApiResponse(data=chat_service.search_conversations(current.id, q, db))


@router.patch("/{cid}/title", response_model=ApiResponse[ConversationOut])
def update_title(
    cid: int,
    up: ConversationTitleUpdate,
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    out = chat_service.update_conversation_title(current, cid, up, db)
    if out is None:
        raise HTTPException(status_code=404, detail="会话不存在")
    return ApiResponse(data=out)


@router.delete("/{cid}", response_model=ApiResponse[dict])
def delete_conv(
    cid: int,
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    ok = chat_service.delete_conversation(current, cid, db)
    if not ok:
        raise HTTPException(status_code=404, detail="会话不存在")
    return ApiResponse(data={"deleted": True})


@router.get("/{cid}/messages", response_model=ApiResponse[list[MessageOut]])
def list_msgs(
    cid: int,
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return ApiResponse(data=chat_service.list_messages(current, cid, db))


# -------------- 聊天 --------------

@router.post("/chat", response_model=ApiResponse[ChatResponse])
def chat_sync(
    req: ChatRequest,
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """同步聊天（非流式；调试/简单场景用）。"""
    return ApiResponse(data=chat_service.chat_sync(current, req, db))


@router.post("/chat/stream")
async def chat_stream(
    req: ChatRequest,
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """SSE 流式聊天。事件：start / delta / error / end。"""
    gen = chat_service.chat_stream(current, req, db)
    return StreamingResponse(
        gen,
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


# -------------- RAG 检索（调试） --------------

@router.post("/rag/search", response_model=ApiResponse[RagSearchOut])
def rag_search_handler(
    payload: RagSearchIn,
    current: User = Depends(get_current_user),
):
    """直接走 RAG 相似度检索（不触发大模型，便于调试召回）。"""
    return ApiResponse(data=rag_search(current.id, payload.query, top_k=payload.top_k))
