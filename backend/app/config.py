"""应用配置：从环境变量读取，统一集中管理。"""
from functools import lru_cache
from typing import List

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """全局配置。本地开发用 .env 文件覆盖默认值。"""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # 应用
    APP_NAME: str = "大学生学习与求职智能助手"
    APP_VERSION: str = "0.1.0"
    DEBUG: bool = True
    API_V1_PREFIX: str = "/api/v1"

    # MySQL（Docker compose 默认：campus-mysql:3306，root/campus123）
    # 若 DATABASE_URL 非空则直接用之（如 sqlite:///./dev.db 用于本地零依赖开发）
    DATABASE_URL: str | None = None
    MYSQL_HOST: str = "127.0.0.1"
    MYSQL_PORT: int = 3306
    MYSQL_USER: str = "root"
    MYSQL_PASSWORD: str = "campus123"
    MYSQL_DATABASE: str = "campus_assistant"
    DB_ECHO: bool = False

    # Redis（本地服务，默认 6379）
    REDIS_HOST: str = "127.0.0.1"
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0
    REDIS_PASSWORD: str = ""

    # JWT
    JWT_SECRET_KEY: str = "change-me-in-production-please"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24  # 1 天

    @model_validator(mode="after")
    def _validate_jwt_secret(self) -> "Settings":
        # 生产环境（DEBUG=False）禁止使用默认密钥，避免 token 可被伪造
        if not self.DEBUG and self.JWT_SECRET_KEY == "change-me-in-production-please":
            raise ValueError(
                "生产环境禁止使用默认 JWT_SECRET_KEY，请通过环境变量设置随机密钥"
            )
        return self

    # 跨域：前端开发地址
    CORS_ORIGINS: List[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]

    # Chroma：优先 HTTP 服务（Docker compose 默认 http://127.0.0.1:8001）；留空则嵌入式目录
    CHROMA_SERVER_URL: str = "http://127.0.0.1:8001"
    CHROMA_PERSIST_DIR: str = "./chroma_db"
    CHROMA_TENANT: str = "default_tenant"
    CHROMA_DATABASE: str = "default_database"

    # 文档上传：本地持久化目录、单个文件最大 MB
    DOC_STORAGE_DIR: str = "./data/documents"
    DOC_MAX_MB: int = 50

    # 图片上传（多模态用）：本地保存目录 + URL 前缀
    UPLOAD_STORAGE_DIR: str = "./uploads"
    UPLOAD_URL_BASE: str = "/uploads"
    UPLOAD_MAX_MB: int = 8

    # Embedding（Chroma 建索引、RAG 检索用）——默认 BAAI/bge-small-zh-v1.5，GPU/CPU 都能跑
    EMBED_MODEL_NAME: str = "BAAI/bge-small-zh-v1.5"
    EMBED_DEVICE: str = "cpu"
    EMBED_SHOW_PROGRESS: bool = False
    EMBED_NORMALIZE: bool = True

    # LLM 提供商："deepseek" / "openai" / "dashscope"；不配 key 则走 echo（回显调试）
    LLM_PROVIDER: str = "deepseek"
    LLM_MODEL: str = "deepseek-chat"
    LLM_TEMPERATURE: float = 0.7
    LLM_MAX_TOKENS: int = 4096

    # RAG
    RAG_CHUNK_SIZE: int = 512
    RAG_CHUNK_OVERLAP: int = 64
    RAG_TOP_K: int = 4
    # 相关度阈值：Chroma 距离（越小越相关），超过该值视为不相关并丢弃
    RAG_MIN_SCORE: float = 1.5

    # 大模型 API（后续模块填充）
    DEEPSEEK_API_KEY: str = ""
    DEEPSEEK_BASE_URL: str = "https://api.deepseek.com/v1"
    DEEPSEEK_MODEL: str = "deepseek-chat"
    # 视觉模型（仅在用户消息带 image_url 时按需切换）
    DEEPSEEK_VISION_MODEL: str = "deepseek-v4-flash-vision-exp"

    DASHSCOPE_API_KEY: str = ""  # 通义千问
    OPENAI_API_KEY: str = ""  # GPT-4V 多模态
    OPENAI_BASE_URL: str = "https://api.openai.com/v1"

    # 第三方搜索 API
    BOCHA_API_KEY: str = ""  # 博查 AI 搜索（国内可用，https://open.bochaai.com 注册）

    @property
    def sqlalchemy_database_url(self) -> str:
        # 优先用 DATABASE_URL（可指向 sqlite:///./dev.db 等任意 SQLAlchemy URL）
        if self.DATABASE_URL:
            return self.DATABASE_URL
        return (
            f"mysql+pymysql://{self.MYSQL_USER}:{self.MYSQL_PASSWORD}"
            f"@{self.MYSQL_HOST}:{self.MYSQL_PORT}/{self.MYSQL_DATABASE}?charset=utf8mb4"
        )

    @property
    def redis_url(self) -> str:
        auth = f":{self.REDIS_PASSWORD}@" if self.REDIS_PASSWORD else ""
        return f"redis://{auth}{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
