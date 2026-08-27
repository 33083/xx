"""FastAPI 应用入口。

启动开发服务器::

    uvicorn app.main:app --reload --port 8000
"""
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from app.api.v1 import api_router
from app.config import settings
from app.database import init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 启动：建表（开发期自动）
    init_db()
    yield


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="基于大模型的大学生学习与求职智能助手系统",
    lifespan=lifespan,
)

# 跨域：允许前端开发地址访问
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 全局限流中间件：单 IP 300 次/分钟，防恶意刷接口
@app.middleware("http")
async def global_rate_limit(request: Request, call_next):
    from app.core.ratelimit import LIMITER, client_ip

    if not LIMITER.allow(f"global_ip:{client_ip(request)}", 300, 60):
        return JSONResponse(
            status_code=429,
            content={"detail": "请求过于频繁，请稍后再试"},
            headers={"Retry-After": "60"},
        )
    return await call_next(request)


# 路由
app.include_router(api_router, prefix=settings.API_V1_PREFIX)

# 静态文件：让上传的图片可以通过 /uploads/... 直接访问
# 必须在 mount 之前确保目录存在（StaticFiles 在模块加载时即检查目录）
os.makedirs(settings.UPLOAD_STORAGE_DIR, exist_ok=True)
app.mount(
    settings.UPLOAD_URL_BASE,
    StaticFiles(directory=settings.UPLOAD_STORAGE_DIR),
    name="uploads",
)


@app.get("/", tags=["root"])
def root():
    return {"app": settings.APP_NAME, "version": settings.APP_VERSION, "docs": "/docs"}
