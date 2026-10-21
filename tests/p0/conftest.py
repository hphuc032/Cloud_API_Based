"""Real PostgreSQL and production auth dependencies; no create_all or auth override."""
import os
import secrets
from urllib.parse import urlparse

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text, create_engine

# Destructive fixtures must never be pointed at an application database.
url = urlparse(os.environ.get("DATABASE_URL", ""))
if (os.environ.get("P0_ISOLATED") != "1" or url.hostname != "postgres"
        or url.path != "/p0_baseline" or os.environ.get("APP_ENV") != "test"):
    raise RuntimeError("P0 requires the isolated Compose test database")

from main import app
from app.auth.security import create_access_token, hash_password
from app.database.session import SessionLocal, engine
from app.models import User, UserRole, Product


@pytest.fixture(scope="session")
def password():
    return "P0!" + secrets.token_hex(16)


@pytest.fixture(scope="session")
def password_hash(password):
    return hash_password(password)


@pytest.fixture(autouse=True)
def clean_database():
    # P1 runs application requests as app_runtime; fixture cleanup is privileged test tooling.
    admin_url = os.environ.get("P0_ADMIN_DATABASE_URL")
    cleanup_engine = create_engine(admin_url) if admin_url else engine
    with cleanup_engine.begin() as connection:
        assert connection.scalar(text("select current_database()")) == "p0_baseline"
        connection.execute(text(
            "TRUNCATE audit_logs, order_items, orders, refresh_tokens, products, "
            "categories, users RESTART IDENTITY CASCADE"))
        if connection.scalar(text("SELECT to_regclass('public.webhook_receipts')")):
            connection.execute(text('TRUNCATE webhook_receipts'))
    if admin_url:
        cleanup_engine.dispose()
    yield


@pytest.fixture
def db():
    with SessionLocal() as session:
        yield session


@pytest.fixture
def client():
    with TestClient(app, raise_server_exceptions=False) as value:
        yield value


@pytest.fixture
def users(db, password_hash):
    result = {}
    for name in ("customer", "customer_b", "staff", "admin"):
        user = User(email=f"{name}@example.com", username=name,
                    hashed_password=password_hash,
                    role=UserRole.customer if name == "customer_b" else UserRole(name))
        db.add(user)
        result[name] = user
    db.commit()
    for user in result.values():
        db.refresh(user)
    return result


@pytest.fixture
def headers(users):
    def make(role):
        if role == "anonymous":
            return {}
        user = users[role]
        return {"Authorization": "Bearer " + create_access_token(
            {"sub": str(user.id), "role": user.role.value})}
    return make


@pytest.fixture
def product(db, users):
    value = Product(sku="P0-SEED", name="Baseline product", price="12.50",
                    stock_quantity=100, created_by=users["staff"].id)
    db.add(value)
    db.commit()
    db.refresh(value)
    return value


@pytest.fixture
def login(client, users, password):
    def authenticate(role="customer"):
        response = client.post("/api/v1/auth/login", data={
            "username": users[role].email, "password": password})
        assert response.status_code == 200
        return response.json()
    return authenticate


@pytest.fixture
def orders(client, headers, product):
    result = {}
    for name in ("customer", "customer_b"):
        response = client.post("/api/v1/orders/", headers=headers(name), json={
            "items": [{"product_id": str(product.id), "quantity": 2}],
            "shipping_name": name})
        assert response.status_code == 201
        result[name] = response.json()["id"]
    return result
