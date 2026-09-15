"""pytest 公共 fixtures。"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base, get_db
from app.main import app


@pytest.fixture(scope="session")
def db_engine():
    """测试用 SQLite 内存数据库。"""
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    yield engine
    Base.metadata.drop_all(engine)


@pytest.fixture(scope="function")
def db_session(db_engine):
    """每个测试函数独立的数据库 session。"""
    conn = db_engine.connect()
    trans = conn.begin()
    Session = sessionmaker(bind=conn)
    session = Session()

    def override_get_db():
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = override_get_db
    yield session
    app.dependency_overrides.clear()
    if trans.is_active:
        trans.rollback()
    conn.close()


@pytest.fixture(scope="function")
def client():
    """FastAPI 测试客户端。"""
    with TestClient(app) as c:
        yield c
