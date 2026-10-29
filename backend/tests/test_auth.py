from app.config import get_settings
from app.modules.core.models import User
from sqlalchemy import select
from app.modules.core.schemas import Credentials
from app.modules.core.service import create_user


def test_cli_provisioned_login_refresh_logout(client, db):
    credentials = {"email": "person@example.com", "password": "my-secure-password"}
    create_user(db, Credentials(**credentials))
    response = client.post("/api/core/auth/login", json=credentials)
    assert response.status_code == 200
    assert "httponly" in response.headers["set-cookie"].lower()
    assert f"Max-Age={get_settings().refresh_token_days * 86400}" in response.headers["set-cookie"]
    user = db.scalar(select(User))
    assert user.password_hash.startswith("$argon2")
    assert "password_hash" not in response.text
    old_refresh = client.cookies.get("refresh_token")
    assert client.get("/api/core/auth/me").status_code == 401
    assert client.post("/api/core/auth/login", json={**credentials, "password": "incorrect-password"}).status_code == 401
    assert client.post("/api/core/auth/login", json=credentials).status_code == 200
    token = client.cookies.get("refresh_token")
    response = client.post("/api/core/auth/refresh")
    assert response.status_code == 200
    assert client.cookies.get("refresh_token") != token
    client.cookies.set("refresh_token", token, domain="testserver.local", path="/api/core/auth")
    assert client.post("/api/core/auth/refresh").status_code == 401
    client.cookies.clear()
    client.cookies.set("refresh_token", old_refresh, domain="testserver.local", path="/api/core/auth")
    assert client.post("/api/core/auth/logout").status_code == 200
    assert client.post("/api/core/auth/refresh").status_code == 401


def test_public_signup_disabled_even_for_direct_requests(client, db):
    for payload in ({"email": "new@example.com", "password": "a-long-password"}, {}, {"anything": "else"}):
        assert client.post("/api/core/auth/register", json=payload).status_code == 404
    assert db.scalar(select(User)) is None
    assert "/api/core/auth/register" not in client.get("/openapi.json").json()["paths"]


def test_login_rate_limit(client):
    settings = get_settings()
    original = settings.login_attempts
    settings.login_attempts = 2
    try:
        payload = {"email": "missing@example.com", "password": "incorrect-password"}
        assert client.post("/api/core/auth/login", json=payload).status_code == 401
        assert client.post("/api/core/auth/login", json=payload).status_code == 401
        response = client.post("/api/core/auth/login", json=payload)
        assert response.status_code == 429
        assert response.headers["retry-after"]
    finally:
        settings.login_attempts = original
