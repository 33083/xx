"""轻量限流：固定窗口计数。

- Redis 后端（优先）：多进程/多机共享计数，重启不清零，适合生产环境。
- 内存后端（兜底）：Redis 不可用时自动回退，单进程可用，保证功能不中断。

对外接口保持一致：allow / over_limit / reset，以及 FastAPI 依赖 rate_limit_ip。
"""
from __future__ import annotations

import threading
import time

from fastapi import HTTPException, Request

from app.config import settings


# ---------------------------------------------------------------------------
# Redis 客户端（延迟初始化，避免启动时强依赖 Redis）
# ---------------------------------------------------------------------------

def _get_redis_client():
    """创建 Redis 客户端；连接失败抛异常（由调用方决定回退）。"""
    import redis as redis_lib

    return redis_lib.Redis.from_url(
        settings.redis_url,
        socket_connect_timeout=1.5,
        socket_timeout=2.0,
        decode_responses=True,
    )


# ---------------------------------------------------------------------------
# 限流器
# ---------------------------------------------------------------------------

class RateLimiter:
    def __init__(self) -> None:
        self._hits: dict[str, list[float]] = {}   # 内存兜底计数
        self._lock = threading.Lock()
        self._redis = None
        self._redis_probed = False  # 是否已探测过 Redis（避免反复重连）

    # ---------------- Redis 后端 ----------------
    def _rdb(self):
        """返回可用 Redis 客户端，或 None（连不上则回退内存）。"""
        if self._redis_probed:
            return self._redis
        self._redis_probed = True
        try:
            client = _get_redis_client()
            client.ping()
            self._redis = client
        except Exception:
            self._redis = None
        return self._redis

    def _redis_allow(self, rdb, key: str, limit: int, window: float) -> bool:
        """Redis 固定窗口：INCR + 首次设置过期。返回窗口内是否允许。"""
        try:
            rk = f"ratelimit:{key}"
            pipe = rdb.pipeline()
            pipe.incr(rk)
            pipe.expire(rk, max(1, int(window)))
            count, _ = pipe.execute()
            return int(count) <= limit
        except Exception:
            # Redis 中途故障：回退内存计数，保证限流不失效
            return self._mem_allow(key, limit, window)

    def _redis_over_limit(self, rdb, key: str, limit: int, window: float) -> bool:
        try:
            rk = f"ratelimit:{key}"
            count = rdb.get(rk)
            return int(count or 0) >= limit
        except Exception:
            return self._mem_over_limit(key, limit, window)

    def _redis_reset(self, rdb, key: str) -> None:
        try:
            rdb.delete(f"ratelimit:{key}")
        except Exception:
            self._mem_reset(key)

    # ---------------- 内存兜底 ----------------
    def _prune(self, key: str, window: float, now: float | None = None) -> None:
        now = time.time() if now is None else now
        arr = self._hits.get(key)
        if arr is None:
            return
        self._hits[key] = [t for t in arr if t > now - window]

    def _mem_allow(self, key: str, limit: int, window: float) -> bool:
        with self._lock:
            now = time.time()
            self._prune(key, window, now)
            arr = self._hits.setdefault(key, [])
            if len(arr) >= limit:
                return False
            arr.append(now)
            return True

    def _mem_over_limit(self, key: str, limit: int, window: float) -> bool:
        with self._lock:
            now = time.time()
            self._prune(key, window, now)
            return len(self._hits.get(key, [])) >= limit

    def _mem_reset(self, key: str) -> None:
        with self._lock:
            self._hits.pop(key, None)

    # ---------------- 对外接口 ----------------
    def allow(self, key: str, limit: int, window: float) -> bool:
        """记录一次访问；若窗口内次数已达上限则返回 False。"""
        rdb = self._rdb()
        if rdb is not None:
            return self._redis_allow(rdb, key, limit, window)
        return self._mem_allow(key, limit, window)

    def over_limit(self, key: str, limit: int, window: float) -> bool:
        """只查询窗口内次数是否已达上限（不记录）。"""
        rdb = self._rdb()
        if rdb is not None:
            return self._redis_over_limit(rdb, key, limit, window)
        return self._mem_over_limit(key, limit, window)

    def reset(self, key: str) -> None:
        """清空某个 key 的计数（如登录成功后重置失败计数）。"""
        rdb = self._rdb()
        if rdb is not None:
            self._redis_reset(rdb, key)
        else:
            self._mem_reset(key)


LIMITER = RateLimiter()


def client_ip(request: Request) -> str:
    """取客户端 IP：优先 X-Forwarded-For（反代场景），否则直连地址。"""
    fwd = request.headers.get("x-forwarded-for", "")
    if fwd:
        return fwd.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def rate_limit_ip(limit: int, window: float):
    """FastAPI 依赖：按 IP 限流，超限抛 429。"""
    def dep(request: Request) -> None:
        if not LIMITER.allow(f"ip:{client_ip(request)}", limit, window):
            raise HTTPException(status_code=429, detail="请求过于频繁，请稍后再试")

    return dep
