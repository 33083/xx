"""认证接口冒烟测试。"""
from app.core.security import create_access_token, hash_password, verify_password
from app.models.user import User


def test_password_hash():
    """密码哈希与校验。"""
    plain = "TestPass123"
    hashed = hash_password(plain)
    assert hashed != plain
    assert verify_password(plain, hashed) is True
    assert verify_password("wrong", hashed) is False


def test_create_and_decode_token():
    """JWT 生成与解码。"""
    token = create_access_token("testuser", 1, "student")
    assert token is not None
    assert len(token) > 20


def test_login_endpoint(client, db_session):
    """登录端点可达性测试。"""
    # 先注册一个用户
    user = User(
        username="testuser",
        email="testuser@test.com",
        nickname="测试",
        hashed_password=hash_password("TestPass123"),
        role="student",
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()

    # 测试登录
    resp = client.post(
        "/api/v1/auth/login",
        json={"account": "testuser", "password": "TestPass123"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "access_token" in data
    assert data["username"] == "testuser"


def test_login_wrong_password(client, db_session):
    """错误密码登录失败。"""
    user = User(
        username="testuser2",
        email="testuser2@test.com",
        nickname="测试2",
        hashed_password=hash_password("TestPass123"),
        role="student",
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()

    resp = client.post(
        "/api/v1/auth/login",
        json={"account": "testuser2", "password": "wrongpassword"},
    )
    assert resp.status_code == 401
