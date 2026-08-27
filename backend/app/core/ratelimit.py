"""轻量内存限流：固定窗口计数器。用于接口限流与登录防爆破。

生产环境可替换为 Redis 实现（接口相同），当前用进程内 dict + 锁即可。
"""
from __future__ import annotations

import threading
import time

from fastapi import HTTPException, Request


class RateLimiter:
    def __init__(self) -> None:
        self._hits: dict[str, list[float]] = {}
        self._lock = threading.Lock()

    def _prune(self, key: str, window: float, now: float | None = None) -> None:
        now = time.time() if now is None else now
        arr = self._hits.get(key)
        if arr is None:
            return
        self._hits[key] = [t for t in arr if t > now - window]

    def allow(self, key: str, limit: int, window: float) -> bool:
        """记录一次访问；若窗口内次数已达上限则返回 False。"""
        with self._lock:
            now = time.time()
            self._prune(key, window, now)
            arr = self._hits.setdefault(key, [])
            if len(arr) >= limit:
                return False
            arr.append(now)
            return True

    def over_limit(self, key: str, limit: int, window: float) -> bool:
        """只查询窗口内次数是否已达上限（不记录）。"""
        with self._lock:
            now = time.time()
            self._prune(key, window, now)
            return len(self._hits.get(key, [])) >= limit

    def reset(self, key: str) -> None:
        with self._lock:
            self._hits.pop(key, None)


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
