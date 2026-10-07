from decimal import Decimal
from uuid import UUID

import pytest
from app.models import Order, Product, UserRole
from baseline import KnownBaselineDefect, expected_status

ROLES = ["anonymous", "customer", "staff", "admin"]


@pytest.mark.parametrize("role", ROLES)
def test_product_crud_authorization(client, headers, product, users, db, role):
    auth = headers(role)
    assert client.get("/api/v1/products/", headers=auth).status_code == 200
    assert client.get(f"/api/v1/products/{product.id}", headers=auth).status_code == 200
    permitted = role in ("staff", "admin")
    denied = 401 if role == "anonymous" else 403
    response = client.post("/api/v1/products/", headers=auth, json={
        "sku": "NEW", "name": "Created", "price": 20, "stock_quantity": 4})
    assert response.status_code == (201 if permitted else denied)
    if permitted:
        created = db.get(Product, UUID(response.json()["id"]))
        assert created.created_by == users[role].id
    response = client.patch(f"/api/v1/products/{product.id}", headers=auth,
                            json={"price": 25, "stock_quantity": 9})
    assert response.status_code == (200 if permitted else denied)
    db.refresh(product)
    assert product.price == Decimal("25" if permitted else "12.50")
    assert client.delete(f"/api/v1/products/{product.id}", headers=auth).status_code == (
        204 if permitted else denied)
    db.refresh(product)
    assert product.is_active is (not permitted)
    assert client.get(f"/api/v1/products/{product.id}").status_code == (404 if permitted else 200)


@pytest.mark.parametrize("role", ROLES)
def test_order_create_authorization_and_server_ownership(client, headers, users, product, db, role):
    response = client.post("/api/v1/orders/", headers=headers(role), json={
        "user_id": str(users["customer_b"].id),
        "items": [{"product_id": str(product.id), "quantity": 3}]})
    assert response.status_code == (401 if role == "anonymous" else 201)
    db.refresh(product)
    assert product.stock_quantity == (100 if role == "anonymous" else 97)
    if role != "anonymous":
        order = db.get(Order, UUID(response.json()["id"]))
        assert order.user_id == users[role].id
        assert order.total_amount == Decimal("37.50")
        assert len(order.order_items) == 1
        assert order.order_items[0].product_id == product.id


@pytest.mark.parametrize("role", ROLES)
def test_order_list_read_status_authorization(client, headers, orders, db, role):
    auth = headers(role)
    response = client.get("/api/v1/orders/", headers=auth)
    assert response.status_code == (401 if role == "anonymous" else 200)
    if role != "anonymous":
        expected = {orders["customer"]} if role == "customer" else set(orders.values())
        assert {item["id"] for item in response.json()["items"]} == expected
        assert response.json()["total"] == len(expected)
    for owner, order_id in orders.items():
        response = client.get(f"/api/v1/orders/{order_id}", headers=auth)
        expected = 401 if role == "anonymous" else (
            403 if role == "customer" and owner == "customer_b" else 200)
        assert response.status_code == expected
        if expected == 200:
            assert response.json()["items"][0]["subtotal"] == 25
        response = client.patch(f"/api/v1/orders/{order_id}/status", headers=auth,
                                json={"status": "shipped"})
        assert response.status_code == (401 if role == "anonymous" else (
            403 if role == "customer" else 200))
        assert db.get(Order, UUID(order_id)).status.value == (
            "shipped" if role in ("staff", "admin") else "pending")


@pytest.mark.parametrize("role", ROLES)
def test_user_self_vs_admin_authorization(client, headers, users, role):
    auth = headers(role)
    own = users["customer" if role == "anonymous" else role]
    response = client.get(f"/api/v1/users/{own.id}", headers=auth)
    assert response.status_code == (401 if role == "anonymous" else 200)
    if response.status_code == 200:
        assert "hashed_password" not in response.json()
        assert "refresh_tokens" not in response.json()
    expected = 401 if role == "anonymous" else (200 if role == "admin" else 403)
    assert client.get(f"/api/v1/users/{users['customer_b'].id}", headers=auth).status_code == expected
    assert client.get("/api/v1/users/", headers=auth).status_code == expected
    assert client.patch(f"/api/v1/users/{users['customer_b'].id}", headers=auth,
                        json={"is_verified": True}).status_code == expected


def test_admin_self_protection_and_db_role_active_authority(client, headers, users, db):
    admin = headers("admin")
    path = f"/api/v1/users/{users['admin'].id}"
    for change in ({"role": "customer"}, {"is_active": False}, {}):
        assert client.patch(path, headers=admin, json=change).status_code == 400
    # Token still says customer; current PostgreSQL role controls authorization.
    customer = headers("customer")
    users["customer"].role = UserRole.admin
    db.commit()
    assert client.get("/api/v1/users/", headers=customer).status_code == 200
    users["customer"].role = UserRole.customer
    db.commit()
    assert client.get("/api/v1/users/", headers=customer).status_code == 403
    users["customer"].is_active = False
    db.commit()
    assert client.get("/api/v1/auth/me", headers=customer).status_code == 401


def test_invalid_orders_do_not_deduct_stock(client, headers, product, db):
    auth = headers("customer")
    for quantity, expected in [(0, 422), (101, 422)]:
        assert client.post("/api/v1/orders/", headers=auth, json={
            "items": [{"product_id": str(product.id), "quantity": quantity}]
        }).status_code == expected
    product.stock_quantity = 1
    db.commit()
    assert client.post("/api/v1/orders/", headers=auth, json={
        "items": [{"product_id": str(product.id), "quantity": 2}]
    }).status_code == 400
    db.refresh(product)
    assert product.stock_quantity == 1
    assert db.query(Order).count() == 0


@pytest.mark.parametrize("role", ["staff", "admin"])
def test_current_order_status_policy(client, headers, orders, role):
    path = f"/api/v1/orders/{orders['customer']}"
    # Current policy allows any enum value, including backwards transitions.
    for status in ("confirmed", "processing", "shipped", "delivered", "cancelled", "refunded", "pending"):
        assert client.patch(path + "/status", headers=headers(role), json={"status": status}).status_code == 200
        assert client.get(path, headers=headers(role)).json()["status"] == status
    assert client.patch(path + "/status", headers=headers(role), json={"status": "not-a-status"}).status_code == 422


@pytest.mark.defect
@pytest.mark.xfail(reason="P0-D06: explicit null product price causes HTTP 500", raises=KnownBaselineDefect)
def test_defect_product_null_field(client, headers, product):
    response = client.patch(f"/api/v1/products/{product.id}", headers=headers("staff"), json={"price": None})
    expected_status(response, current=500, desired=422)


@pytest.mark.defect
@pytest.mark.xfail(reason="P0-D07: explicit null user role causes HTTP 500", raises=KnownBaselineDefect)
def test_defect_user_null_field(client, headers, users):
    response = client.patch(f"/api/v1/users/{users['customer'].id}", headers=headers("admin"), json={"role": None})
    expected_status(response, current=500, desired=422)
