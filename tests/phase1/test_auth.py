import datetime

import jwt
import pytest

from app.core.config import get_settings


def test_register_login_me(client):
    r = client.post("/api/v1/auth/register", json={"name": "Arjun", "email": "Arjun@Example.com", "password": "supersecret1", "monthly_income": 90000.5})
    assert r.status_code == 201
    body = r.json()
    assert body["email"] == "arjun@example.com" and body["monthly_income"] == 90000.5 and "password" not in body and "password_hash" not in body
    login = client.post("/api/v1/auth/login", data={"username": "arjun@example.com", "password": "supersecret1"})
    assert login.status_code == 200 and login.json()["token_type"] == "bearer"
    me = client.get("/api/v1/users/me", headers={"Authorization": f"Bearer {login.json()['access_token']}"})
    assert me.status_code == 200 and me.json()["name"] == "Arjun"


def test_password_is_hashed_not_plaintext(client, db_session):
    from app.models import User

    client.post("/api/v1/auth/register", json={"name": "A", "email": "a@x.com", "password": "supersecret1"})
    u = db_session.query(User).one()
    assert u.password_hash != "supersecret1" and u.password_hash.startswith("$2")


def test_duplicate_email_conflict_and_validation(client):
    body = {"name": "A", "email": "a@x.com", "password": "supersecret1"}
    assert client.post("/api/v1/auth/register", json=body).status_code == 201
    assert client.post("/api/v1/auth/register", json=body).status_code == 409
    assert client.post("/api/v1/auth/register", json={**body, "email": "not-an-email"}).status_code == 422
    assert client.post("/api/v1/auth/register", json={**body, "email": "b@x.com", "password": "short"}).status_code == 422
    assert client.post("/api/v1/auth/register", json={**body, "email": "b@x.com", "password": "x" * 80}).status_code == 422


def test_wrong_password_and_unknown_user_401(client):
    client.post("/api/v1/auth/register", json={"name": "A", "email": "a@x.com", "password": "supersecret1"})
    assert client.post("/api/v1/auth/login", data={"username": "a@x.com", "password": "wrongpass1"}).status_code == 401
    assert client.post("/api/v1/auth/login", data={"username": "nobody@x.com", "password": "supersecret1"}).status_code == 401


@pytest.mark.parametrize("path", ["/api/v1/accounts", "/api/v1/transactions", "/api/v1/budgets", "/api/v1/dashboard", "/api/v1/users/me", "/api/v1/budget-alerts"])
def test_protected_endpoints_require_token(client, path):
    assert client.get(path).status_code == 401


def test_invalid_expired_and_forged_tokens_rejected(client, auth_headers):
    s = get_settings()
    expired = jwt.encode({"sub": "1", "exp": datetime.datetime.now(datetime.UTC) - datetime.timedelta(minutes=1)}, s.secret_key, algorithm="HS256")
    forged = jwt.encode({"sub": "1", "exp": datetime.datetime.now(datetime.UTC) + datetime.timedelta(hours=1)}, "wrong-secret-key-0123456789012345678", algorithm="HS256")
    no_exp = jwt.encode({"sub": "1"}, s.secret_key, algorithm="HS256")
    for tok in ("garbage", expired, forged, no_exp):
        assert client.get("/api/v1/users/me", headers={"Authorization": f"Bearer {tok}"}).status_code == 401
    assert client.get("/api/v1/users/me", headers=auth_headers).status_code == 200


def test_token_for_deleted_user_rejected(client):
    s = get_settings()
    tok = jwt.encode({"sub": "4242", "exp": datetime.datetime.now(datetime.UTC) + datetime.timedelta(hours=1)}, s.secret_key, algorithm="HS256")
    assert client.get("/api/v1/users/me", headers={"Authorization": f"Bearer {tok}"}).status_code == 401


def test_token_lifetime_is_24_hours(auth_token):
    p = jwt.decode(auth_token, get_settings().secret_key, algorithms=["HS256"])
    assert p["exp"] - p["iat"] == 24 * 3600


def test_update_profile(client, auth_headers):
    r = client.patch("/api/v1/users/me", json={"name": "New Name", "phone": "999", "monthly_income": 120000}, headers=auth_headers)
    assert r.status_code == 200 and r.json()["name"] == "New Name" and r.json()["monthly_income"] == 120000.0


def test_health_and_request_id_header(client):
    r = client.get("/api/v1/health")
    assert r.status_code == 200 and r.json() == {"status": "ok"} and r.headers["x-request-id"].startswith("req_")
