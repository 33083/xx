"""SQLAlchemy 数据库引擎与会话。

用法::

    from app.database import SessionLocal, Base, get_db

    with SessionLocal() as db:
        ...
"""
from typing import Generator

from sqlalchemy import BigInteger, Integer, create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.config import settings


# 跨库自增主键整型：MySQL 用 BIGINT，SQLite 用 INTEGER（才能自增）
BigInt = BigInteger().with_variant(Integer(), "sqlite")


class Base(DeclarativeBase):
    """所有 ORM 模型的基类。"""

    pass


_db_url = settings.sqlalchemy_database_url
_is_sqlite = _db_url.startswith("sqlite")

_engine_kwargs: dict = {"echo": settings.DB_ECHO}
if _is_sqlite:
    _engine_kwargs["connect_args"] = {"check_same_thread": False}
else:
    _engine_kwargs["pool_pre_ping"] = True
    _engine_kwargs["pool_recycle"] = 3600

engine = create_engine(_db_url, **_engine_kwargs)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db() -> Generator:
    """FastAPI 依赖：每请求一个数据库会话。"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    """建表：开发期用 create_all 直接建。生产环境用 Alembic 迁移。"""
    # 触发模型导入，确保 Base.metadata 已加载所有表
    from app import models  # noqa: F401

    Base.metadata.create_all(bind=engine)
    _migrate_documents_md5()
    _migrate_columns()


def _migrate_documents_md5() -> None:
    """轻量迁移：给已存在的 documents 表补 md5 列（create_all 不会改旧表）。"""
    from sqlalchemy import inspect, text

    insp = inspect(engine)
    if "documents" not in insp.get_table_names():
        return
    cols = {c["name"] for c in insp.get_columns("documents")}
    if "md5" not in cols:
        with engine.begin() as conn:
            conn.execute(text("ALTER TABLE documents ADD COLUMN md5 VARCHAR(64)"))
        print("[migrate] documents.md5 column added")


def _migrate_columns() -> None:
    """轻量迁移：给 users/conversations 补长期记忆列（create_all 不会改旧表）。"""
    from sqlalchemy import inspect, text

    insp = inspect(engine)
    add_sqls: list[tuple[str, str]] = []
    if "users" in insp.get_table_names():
        cols = {c["name"] for c in insp.get_columns("users")}
        if "profile" not in cols:
            add_sqls.append(("users", "profile"))
    if "conversations" in insp.get_table_names():
        cols = {c["name"] for c in insp.get_columns("conversations")}
        if "summary" not in cols:
            add_sqls.append(("conversations", "summary"))
    if not add_sqls:
        return
    with engine.begin() as conn:
        for table, col in add_sqls:
            conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {col} TEXT NULL"))
    print(f"[migrate] added columns: {add_sqls}")

