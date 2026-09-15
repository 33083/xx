"""FastAPI 应用入口。

启动开发服务器::

    uvicorn app.main:app --reload --port 8000
"""
import logging
import os
import time as _time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from app.api.v1 import api_router
from app.config import settings
from app.database import init_db

# 结构化日志
logger = logging.getLogger("app")
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL, logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)


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
    # 生产环境（DEBUG=False）关闭 Swagger UI，避免暴露接口结构
    docs_url="/docs" if settings.DEBUG else None,
    redoc_url="/redoc" if settings.DEBUG else None,
    openapi_url="/openapi.json" if settings.DEBUG else None,
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


# 请求日志中间件：记录每个请求的方法、路径、状态码与耗时
@app.middleware("http")
async def request_log(request: Request, call_next):
    start = _time.time()
    response = await call_next(request)
    duration_ms = int((_time.time() - start) * 1000)
    logger.info(
        f"{request.method} {request.url.path} -> {response.status_code} ({duration_ms}ms)"
    )
    return response


# 全局异常处理：捕获未处理异常，返回统一 500 响应并记录日志
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"未捕获异常: {request.method} {request.url.path} - {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"detail": "服务器内部错误，请稍后重试"},
    )


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
