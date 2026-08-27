"""RAG 检索服务：从用户向量库/公共库取 top_k 引用。"""
from __future__ import annotations

from typing import List

from app.config import settings
from app.core.vectorstore import get_shared_vectorstore, get_user_vectorstore
from app.schemas.document import ChunkRef, RagSearchOut


def _docs_to_refs(docs_with_score, source: str = "user") -> List[ChunkRef]:
    hits: List[ChunkRef] = []
    for d, score in docs_with_score:
        meta = d.metadata or {}
        hits.append(ChunkRef(
            doc_id=int(meta.get("doc_id", 0) or 0),
            doc_title=str(meta.get("doc_title", "") or ""),
            chunk_index=int(meta.get("chunk_index", 0) or 0),
            content=d.page_content or "",
            score=float(score),
            source=source,
        ))
    return hits


def _is_collection_missing(exc: Exception) -> bool:
    """集合不存在（如用户还没有文档）属于正常情况，不算检索故障。"""
    msg = str(exc).lower()
    return "not found" in msg or "does not exist" in msg or "no collection" in msg


def rag_search(
    user_id: int, query: str, *, category: str = "all", top_k: int | None = None
) -> RagSearchOut:
    k = top_k or settings.RAG_TOP_K
    user_hits: List = []
    shared_hits: List = []
    rag_ok = False

    # 用户库：按分类过滤（全部时不加过滤）
    user_where: dict | None = None
    if category in ("material", "resume", "interview"):
        user_where = {"category": category}
    try:
        vs_u = get_user_vectorstore(user_id, create_if_missing=False)
        user_hits = vs_u.similarity_search_with_score(query, k=k, where=user_where)
        rag_ok = True
    except Exception as e:
        # 用户还没有文档（集合不存在）属于正常情况，不算故障
        if _is_collection_missing(e):
            rag_ok = True

    # 公共内置知识库：全部分类都会检索，并按分类过滤（material/resume/interview）
    shared_where: dict | None = None
    if category in ("material", "resume", "interview"):
        shared_where = {"category": category}
    try:
        vs_s = get_shared_vectorstore()
        shared_hits = vs_s.similarity_search_with_score(query, k=k, where=shared_where)
        rag_ok = True
    except Exception:
        pass

    combined = _docs_to_refs(user_hits, source="user") + _docs_to_refs(shared_hits, source="shared")
    # 相关度阈值过滤：距离超过 RAG_MIN_SCORE 的片段视为不相关，直接丢弃
    min_score = settings.RAG_MIN_SCORE
    if min_score > 0:
        combined = [r for r in combined if r.score <= min_score]
    combined.sort(key=lambda x: x.score)
    combined = combined[:k]
    return RagSearchOut(query=query, hits=combined, rag_ok=rag_ok)


def build_context_block(refs: List[ChunkRef]) -> str:
    if not refs:
        return ""
    buf = ["<知识库检索片段>"]
    for i, r in enumerate(refs, 1):
        title = r.doc_title or "(未知文档)"
        buf.append(f"[{i}] 文档《{title}》（chunk {r.chunk_index}, 相关度={r.score:.4f}）")
        buf.append(r.content.strip() or "")
        buf.append("")
    buf.append("</知识库检索片段>")
    return "\n".join(buf)
