"""Embedding 工厂：BAAI/bge-small-zh-v1.5 默认模型。

无网/缺依赖时 FallbackHashEmbeddings 兜底，保证链路跑通。
"""
from __future__ import annotations

from functools import lru_cache
from typing import List

from app.config import settings


class FallbackHashEmbeddings:
    dimension: int = 384

    def _embed(self, text: str) -> List[float]:
        import hashlib
        import struct

        v = [0.0] * self.dimension
        for seed in range(8):
            h = hashlib.sha256(f"{seed}:{text}".encode("utf-8", errors="ignore")).digest()
            for i in range(0, min(len(h), self.dimension * 4), 4):
                idx = (i // 4 + seed * 16) % self.dimension
                val = struct.unpack_from("!i", h, i % (len(h) - 3))[0] / 2_147_483_648.0
                v[idx] += val
        s = sum(x * x for x in v) ** 0.5 or 1.0
        return [x / s for x in v]

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        return [self._embed(t) for t in texts]

    def embed_query(self, text: str) -> List[float]:
        return self._embed(text)


@lru_cache(maxsize=1)
def get_embeddings():
    try:
        from langchain_community.embeddings import HuggingFaceBgeEmbeddings

        model_kwargs = {"device": settings.EMBED_DEVICE}
        encode_kwargs = {
            "normalize_embeddings": settings.EMBED_NORMALIZE,
            "show_progress_bar": settings.EMBED_SHOW_PROGRESS,
        }
        return HuggingFaceBgeEmbeddings(
            model_name=settings.EMBED_MODEL_NAME,
            model_kwargs=model_kwargs,
            encode_kwargs=encode_kwargs,
        )
    except Exception:
        pass

    try:
        from langchain_community.embeddings import SentenceTransformerEmbeddings

        return SentenceTransformerEmbeddings(model_name=settings.EMBED_MODEL_NAME)
    except Exception:
        pass

    return FallbackHashEmbeddings()
