from datetime import datetime, timedelta, timezone

import jwt

from app.config import settings


def test_login_ok_and_refresh(client, tenant_factory):
    t = tenant_factory("Acme")
    r = client.post("/v1/auth/login", json={"email": t["email"], "senha": t["senha"]})
    assert r.status_code == 200
    tokens = r.json()
    assert tokens["access_token"] and tokens["refresh_token"]

    r2 = client.post("/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
    assert r2.status_code == 200
    assert r2.json()["access_token"]


def test_login_wrong_password(client, tenant_factory):
    t = tenant_factory("Beta")
    r = client.post("/v1/auth/login", json={"email": t["email"], "senha": "wrong"})
    assert r.status_code == 401


def test_unknown_email_same_error(client):
    r = client.post("/v1/auth/login", json={"email": "nobody@demo.com", "senha": "x"})
    assert r.status_code == 401


def test_protected_requires_valid_token(client):
    assert client.get("/v1/consultas").status_code == 401
    r = client.get("/v1/consultas", headers={"Authorization": "Bearer garbage"})
    assert r.status_code == 401


def test_expired_token_rejected(client, tenant_factory):
    t = tenant_factory("Gamma")
    expired = jwt.encode(
        {
            "sub": t["user_id"],
            "tenant_id": t["tenant_id"],
            "role": "admin",
            "type": "access",
            "exp": datetime.now(timezone.utc) - timedelta(minutes=1),
        },
        settings.jwt_secret,
        algorithm=settings.jwt_alg,
    )
    r = client.get("/v1/consultas", headers={"Authorization": f"Bearer {expired}"})
    assert r.status_code == 401
