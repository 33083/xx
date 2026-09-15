"""健康检查接口。"""
import logging

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db

logger = logging.getLogger("app.health")
router = APIRouter(tags=["health"])


def _check_redis() -> bool:
    """检查 Redis 连通性。"""
    try:
        import redis as redis_lib
        rdb = redis_lib.Redis.from_url(
            settings.redis_url,
            socket_connect_timeout=1.5,
            socket_timeout=2.0,
        )
        rdb.ping()
        return True
    except Exception as e:
        logger.warning(f"Redis health check failed: {e}")
        return False


def _check_chroma() -> bool:
    """检查 Chroma 向量库连通性。"""
    try:
        if not settings.CHROMA_SERVER_URL:
            return True  # 嵌入式模式无需检查
        import chromadb
        from chromadb.config import Settings
        url = settings.CHROMA_SERVER_URL.replace("http://", "").replace("https://", "")
        if ":" in url:
            host, port = url.rsplit(":", 1)
        else:
            host, port = url, 8000
        client = chromadb.HttpClient(
            host=host, port=int(port),
            tenant=settings.CHROMA_TENANT,
            database=settings.CHROMA_DATABASE,
            settings=Settings(anonymized_telemetry=False),
        )
        client.heartbeat()
        return True
    except Exception as e:
        logger.warning(f"Chroma health check failed: {e}")
        return False


@router.get("/health")
def health_check(db: Session = Depends(get_db)):
    """服务存活 + 依赖连通性。"""
    db_ok = True
    try:
        db.execute(text("SELECT 1"))
    except Exception:
        db_ok = False
    redis_ok = _check_redis()
    chroma_ok = _check_chroma()
    all_ok = db_ok and redis_ok and chroma_ok
    return {
        "status": "ok" if all_ok else "degraded",
        "db": "ok" if db_ok else "error",
        "redis": "ok" if redis_ok else "error",
        "chroma": "ok" if chroma_ok else "error",
    }
