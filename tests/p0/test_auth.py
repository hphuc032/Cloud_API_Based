from datetime import datetime, timedelta, timezone
import secrets
from uuid import UUID, uuid4

import pytest
from jose import jwt
from app.auth.security import create_access_token, hash_refresh_token
from app.config import settings
from app.models import RefreshToken, User
from baseline import KnownBaselineDefect, expected_status


@pytest.mark.parametrize("kind", ["missing", "garbage", "wrong_key", "expired", "wrong_type", "no_sub", "unknown_user"])
def test_rejected_access_tokens(client, users, kind):
    claims = {"sub": str(users["customer"].id), "type": "access",
              "exp": datetime.now(timezone.utc) + timedelta(minutes=5)}
    key = settings.SECRET_KEY
    if kind == "wrong_key":
        key = secrets.token_hex(32)
    if kind == "expired":
        claims["exp"] = datetime.now(timezone.utc) - timedelta(seconds=60)
    if kind == "wrong_type":
        claims["type"] = "refresh"
    if kind == "no_sub":
        del claims["sub"]
    if kind == "unknown_user":
        claims["sub"] = str(uuid4())
    token = "invalid.jwt.value" if kind == "garbage" else jwt.encode(claims, key, algorithm="HS256")
    auth = {} if kind == "missing" else {"Authorization": "Bearer " + token}
    response = client.get("/api/v1/auth/me", headers=auth)
    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"


@pytest.mark.parametrize("role", ["customer", "staff", "admin"])
def test_current_login_claims_and_refresh_hash(login, client, db, users, role):
    pair = login(role)
    claims = jwt.decode(pair["access_token"], settings.SECRET_KEY, algorithms=["HS256"])
    assert claims["sub"] == str(users[role].id)
    assert claims["role"] == role
    assert claims["type"] == "access"
    assert claims["exp"] - claims["iat"] == 900
    assert pair["token_type"] == "bearer" and pair["expires_in"] == 900
    stored = db.query(RefreshToken).one()
    assert stored.token_hash == hash_refresh_token(pair["refresh_token"])
    assert stored.token_hash != pair["refresh_token"]
    assert stored.user_id == users[role].id
    response = client.get("/api/v1/auth/me", headers={"Authorization": "Bearer " + pair["access_token"]})
    assert response.status_code == 200 and response.json()["id"] == str(users[role].id)


def test_refresh_rotation_and_reuse(login, client, db):
    old = login()
    response = client.post("/api/v1/auth/refresh", json={"refresh_token": old["refresh_token"]})
    assert response.status_code == 200
    new = response.json()
    assert new["refresh_token"] != old["refresh_token"]
    assert db.query(RefreshToken).filter_by(token_hash=hash_refresh_token(old["refresh_token"])).one().revoked
    assert client.post("/api/v1/auth/refresh", json={"refresh_token": old["refresh_token"]}).status_code == 401
    # Current behavior: replay does not revoke the replacement token/family.
    assert client.post("/api/v1/auth/refresh", json={"refresh_token": new["refresh_token"]}).status_code == 200


@pytest.mark.parametrize("condition", ["unknown", "expired", "revoked", "disabled", "short"])
def test_refresh_rejection(login, client, users, db, condition):
    pair = login()
    raw = pair["refresh_token"]
    stored = db.query(RefreshToken).one()
    if condition == "unknown":
        raw = secrets.token_urlsafe(64)
    elif condition == "expired":
        stored.expires_at = datetime.now(timezone.utc) - timedelta(seconds=60)
    elif condition == "revoked":
        stored.revoked = True
    elif condition == "disabled":
        users["customer"].is_active = False
    else:
        raw = "short"
    db.commit()
    assert client.post("/api/v1/auth/refresh", json={"refresh_token": raw}).status_code == (
        422 if condition == "short" else 401)


def test_logout_revokes_only_owned_refresh_and_keeps_access(login, client):
    a, b = login(), login("customer_b")
    auth = {"Authorization": "Bearer " + a["access_token"]}
    assert client.post("/api/v1/auth/logout", json={"refresh_token": a["refresh_token"]}).status_code == 401
    assert client.post("/api/v1/auth/logout", headers=auth,
                       json={"refresh_token": b["refresh_token"]}).status_code == 204
    assert client.post("/api/v1/auth/refresh", json={"refresh_token": b["refresh_token"]}).status_code == 200
    assert client.post("/api/v1/auth/logout", headers=auth,
                       json={"refresh_token": a["refresh_token"]}).status_code == 204
    assert client.post("/api/v1/auth/refresh", json={"refresh_token": a["refresh_token"]}).status_code == 401
    assert client.get("/api/v1/auth/me", headers=auth).status_code == 200


def test_registration_cannot_assign_admin(client, db, password):
    data = {"email": "new@example.com", "username": "newuser", "password": password,
            "role": "admin", "is_active": False}
    response = client.post("/api/v1/auth/register", json=data)
    assert response.status_code == 201
    user = db.get(User, UUID(response.json()["user_id"]))
    assert user.role.value == "customer" and user.is_active
    assert client.post("/api/v1/auth/register", json=data).status_code == 400


def test_login_lockout(client, users, password):
    for _ in range(5):
        assert client.post("/api/v1/auth/login", data={
            "username": users["customer"].email, "password": secrets.token_hex(20)
        }).status_code == 401
    assert client.post("/api/v1/auth/login", data={
        "username": users["customer"].email, "password": password
    }).status_code == 429


@pytest.mark.defect
@pytest.mark.xfail(reason="P0-D01: signed access JWT without exp is accepted", raises=KnownBaselineDefect)
def test_defect_jwt_requires_exp(client, users):
    token = jwt.encode({"sub": str(users["customer"].id), "type": "access"},
                       settings.SECRET_KEY, algorithm="HS256")
    response = client.get("/api/v1/auth/me", headers={"Authorization": "Bearer " + token})
    expected_status(response, current=200, desired=401)


@pytest.mark.defect
@pytest.mark.xfail(reason="P0-D02: signed non-UUID subject causes HTTP 500", raises=KnownBaselineDefect)
def test_defect_malformed_subject_is_401(client):
    token = create_access_token({"sub": "not-a-uuid"})
    response = client.get("/api/v1/auth/me", headers={"Authorization": "Bearer " + token})
    expected_status(response, current=500, desired=401)
