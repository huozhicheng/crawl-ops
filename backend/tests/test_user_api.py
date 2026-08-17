"""用户 API 的输入校验测试。"""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.v1.users import router as users_router
from app.core.database import get_db


@pytest.fixture
def client():
    """使用最小应用验证请求在访问数据库前被拒绝。"""
    app = FastAPI()
    app.include_router(users_router, prefix="/users")

    def override_get_db():
        yield object()

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app, raise_server_exceptions=False) as test_client:
        yield test_client


@pytest.mark.parametrize("password", ["a" * 73, "密" * 25])
def test_create_user_rejects_passwords_over_bcrypt_byte_limit(client, password):
    response = client.post(
        "/users",
        json={"username": "new-user", "password": password, "email": "new@example.com"},
    )

    assert response.status_code == 422
    assert "72" in response.text


@pytest.mark.parametrize("password", ["a" * 73, "密" * 25])
def test_change_password_rejects_passwords_over_bcrypt_byte_limit(client, password):
    response = client.put(
        "/users/1/password",
        json={"old_password": "current-password", "new_password": password},
    )

    assert response.status_code == 422
    assert "72" in response.text
