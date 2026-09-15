"""RAG 检索服务冒烟测试。"""
from app.services.rag_service import rag_search


def test_rag_search_returns_structure():
    """rag_search 返回 RagSearchOut 结构。"""
    result = rag_search(user_id=99999, query="测试查询", category="all", top_k=2)
    assert hasattr(result, "hits")
    assert hasattr(result, "rag_ok")
    assert isinstance(result.hits, list)
    assert isinstance(result.rag_ok, bool)


def test_rag_search_empty_user():
    """无文档用户检索返回空列表。"""
    result = rag_search(user_id=99999, query="不存在的查询", category="all")
    # 用户 99999 没有文档，hits 应为空
    assert len(result.hits) == 0 or result.rag_ok is False
