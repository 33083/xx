"""向量库工厂：Chroma（HTTP 优先，否则内存兜底）。

为避免对 `langchain-chroma` 包（它硬依赖 numpy<2）的强依赖，这里
直接用原生 chromadb API + 一个薄兼容层对外暴露 LangChain 风格接口：
    - add_texts(texts, metadatas, ids)
    - similarity_search_with_score(query, k) -> List[(Document, score)]
    - _collection -> 底层 chromadb Collection（用于 delete 等高级操作）
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, List, Optional, Sequence

import chromadb
from chromadb import api as chroma_api

from app.config import settings
from app.core.embeddings import get_embeddings

_HTTP_CLIENT = None
_EPHEMERAL_CLIENT = None


def _parse_http(url: str):
    u = url.replace("http://", "").replace("https://", "")
    if ":" in u:
        host, port = u.rsplit(":", 1)
        return host, int(port)
    return u, 8000


def _get_chroma_client() -> chroma_api.ClientAPI:
    global _HTTP_CLIENT, _EPHEMERAL_CLIENT
    if settings.CHROMA_SERVER_URL:
        try:
            if _HTTP_CLIENT is None:
                host, port = _parse_http(settings.CHROMA_SERVER_URL)
                # 服务器与客户端同为 chromadb 1.5.9，默认走 v2 路由（多租户多数据库规范）。
                from chromadb.config import Settings

                s = Settings(anonymized_telemetry=False)
                _HTTP_CLIENT = chromadb.HttpClient(
                    host=host,
                    port=port,
                    tenant=settings.CHROMA_TENANT,
                    database=settings.CHROMA_DATABASE,
                    settings=s,
                )
                _HTTP_CLIENT.heartbeat()
            return _HTTP_CLIENT
        except Exception:
            pass
    if _EPHEMERAL_CLIENT is None:
        _EPHEMERAL_CLIENT = chromadb.EphemeralClient()
    return _EPHEMERAL_CLIENT


def user_collection_name(user_id: int) -> str:
    return f"user_{user_id}_docs"


# ---------------------------------------------------------------------------
# LangChain Document 轻量替代（只需要 page_content + metadata）
# 若 langchain 已可用则优先复用其 Document 类以便后续链路上游兼容
# ---------------------------------------------------------------------------
try:
    from langchain_core.documents import Document  # noqa: F401
except Exception:  # pragma: no cover - 兜底定义
    @dataclass
    class Document:  # type: ignore[no-redef]
        page_content: str
        metadata: Optional[dict] = None


# ---------------------------------------------------------------------------
# chromadb EmbeddingFunction 协议：输入 list[str]，返回 list[list[float]]
# 我们把 LangChain 风格 embeddings 对象（有 embed_documents/embed_query）包一层
# ---------------------------------------------------------------------------
class _ChromaEFAdapter(chromadb.EmbeddingFunction):  # type: ignore[name-defined]
    def __init__(self, lc_embeddings):
        self._lc = lc_embeddings

    def __call__(self, input: Any) -> Any:
        # chromadb v0.4+ / v1.x 传入的总是 list[str]
        if isinstance(input, str):
            texts: Sequence[str] = [input]
        else:
            texts = list(input)
        return self._lc.embed_documents(list(texts))


# ---------------------------------------------------------------------------
# 对外兼容类：保留原 langchain_chroma.Chroma 所用到的最小接口子集
# ---------------------------------------------------------------------------
class ChromaVectorStore:
    """轻量兼容层，等价于原 `langchain_chroma.Chroma`。

    只实现项目实际调用过的三个入口，其它按需补。
    """

    def __init__(
        self,
        client: chroma_api.ClientAPI,
        collection_name: str,
        embedding_function: Any,
        create_collection_if_not_exists: bool = True,
    ) -> None:
        self._client = client
        self._ef = _ChromaEFAdapter(embedding_function)
        if create_collection_if_not_exists:
            self._collection = client.get_or_create_collection(
                name=collection_name,
                embedding_function=self._ef,
            )
        else:
            self._collection = client.get_collection(
                name=collection_name,
                embedding_function=self._ef,
            )

    # ----- 写入 ---------------------------------------------------------
    def add_texts(
        self,
        texts: Iterable[str],
        metadatas: Optional[List[dict]] = None,
        ids: Optional[List[str]] = None,
        **_kwargs: Any,
    ) -> List[str]:
        text_list = list(texts)
        n = len(text_list)
        if ids is None:
            import uuid
            ids = [str(uuid.uuid4()) for _ in range(n)]
        if metadatas is None:
            metadatas = [{} for _ in range(n)]
        elif len(metadatas) < n:
            metadatas = list(metadatas) + [{}] * (n - len(metadatas))
        # chromadb 批量写入，内部会走 embedding_function 计算向量
        self._collection.add(ids=ids, documents=text_list, metadatas=metadatas)
        return ids

    # ----- 检索 ---------------------------------------------------------
    def similarity_search_with_score(
        self, query: str, k: int = 4, where: Optional[dict] = None, **_kwargs: Any
    ) -> List[tuple]:
        query_params: dict = {
            "query_texts": [query],
            "n_results": k,
            "include": ["documents", "metadatas", "distances"],
        }
        if where:
            query_params["where"] = where
        res = self._collection.query(**query_params)
        docs: List[str] = (res.get("documents") or [[]])[0]
        metas: List[Optional[dict]] = (res.get("metadatas") or [[]])[0]
        dists: List[float] = (res.get("distances") or [[]])[0]
        hits: List[tuple] = []
        for i, text in enumerate(docs):
            md = metas[i] if i < len(metas) else None
            score = float(dists[i]) if i < len(dists) else 0.0
            hits.append((Document(page_content=text or "", metadata=md or {}), score))
        return hits


# ---------------------------------------------------------------------------
# 对外工厂函数 —— 保持原签名，返回 ChromaVectorStore 实例
# ---------------------------------------------------------------------------
def get_user_vectorstore(
    user_id: int, *, create_if_missing: bool = True
) -> ChromaVectorStore:
    return ChromaVectorStore(
        client=_get_chroma_client(),
        collection_name=user_collection_name(user_id),
        embedding_function=get_embeddings(),
        create_collection_if_not_exists=create_if_missing,
    )


def get_shared_vectorstore() -> ChromaVectorStore:
    return ChromaVectorStore(
        client=_get_chroma_client(),
        collection_name="shared_interview_knowledge",
        embedding_function=get_embeddings(),
        create_collection_if_not_exists=True,
    )
