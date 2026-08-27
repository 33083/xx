"""v1 路由聚合：所有子路由在此挂载。新增模块时在此追加。"""
from fastapi import APIRouter

from app.api.v1 import auth, conversations, documents, health, skills, uploads, users

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(users.router)
api_router.include_router(documents.router)
api_router.include_router(conversations.router)
api_router.include_router(skills.router)
api_router.include_router(uploads.router)

# 后续模块预留：
# api_router.include_router(mcp.router)
# api_router.include_router(agent.router)
