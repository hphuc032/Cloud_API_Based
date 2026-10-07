"""Upgrade a synthetic P0 database owned by postgres without changing its rows."""
import json
import os
from pathlib import Path
import subprocess
from uuid import uuid4

import psycopg2
from psycopg2 import sql
from sqlalchemy.engine import make_url


def test_existing_p0_database_adoption_preserves_data():
    admin_url = make_url(os.environ["P0_ADMIN_DATABASE_URL"])
    name = "p1_adoption_" + uuid4().hex
    old_url = admin_url.set(database=name).render_as_string(hide_password=False)
    admin = psycopg2.connect(os.environ["P0_ADMIN_DATABASE_URL"])
    admin.autocommit = True
    with admin.cursor() as cur:
        cur.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
    env = dict(os.environ, APP_DB_NAME=name, DATABASE_URL=old_url,
               POSTGRES_PASSWORD_FILE="/run/secrets/postgres_password",
               MIGRATION_PASSWORD_FILE="/run/secrets/migration_password",
               RUNTIME_PASSWORD_FILE="/run/secrets/runtime_password",
               DB_PASSWORD_FILE="/run/secrets/migration_password")

    def command(args):
        result = subprocess.run(args, env=env, capture_output=True, text=True)
        assert result.returncode == 0, "Adoption command failed: " + args[-1]

    def snapshot():
        with psycopg2.connect(old_url) as conn, conn.cursor() as cur:
            result = {}
            for table in ("users", "products", "orders", "order_items", "alembic_version"):
                cur.execute(sql.SQL("SELECT row_to_json(t)::text FROM {} t ORDER BY row_to_json(t)::text").format(sql.Identifier(table)))
                result[table] = cur.fetchall()
            return result

    try:
        # Build the historical schema as postgres using the UNCHANGED initial migration.
        command(["alembic", "upgrade", "head"])
        user_id, product_id, order_id, item_id = [str(uuid4()) for _ in range(4)]
        with psycopg2.connect(old_url) as conn, conn.cursor() as cur:
            cur.execute("INSERT INTO users(id,email,username,hashed_password,role,is_active) "
                        "VALUES (%s,'existing@example.com','existing','synthetic-non-login-fixture','staff',true)", (user_id,))
            cur.execute("INSERT INTO products(id,sku,name,price,created_by) VALUES (%s,'existing','Existing',12.50,%s)",
                        (product_id, user_id))
            cur.execute("INSERT INTO orders(id,user_id,order_number,total_amount,status) VALUES (%s,%s,'existing',25,'shipped')",
                        (order_id, user_id))
            cur.execute("INSERT INTO order_items(id,order_id,product_id,quantity,unit_price) VALUES (%s,%s,%s,2,12.50)",
                        (item_id, order_id, product_id))
        before = snapshot()
        for _ in range(2):
            command(["python", "-m", "deployment.bootstrap"])
            command(["python", "-m", "deployment.migrate"])
            assert snapshot() == before
        runtime_url = admin_url.set(username="app_runtime", database=name,
                                   password=Path("/run/secrets/runtime_password").read_text().strip())
        with psycopg2.connect(runtime_url.render_as_string(hide_password=False)) as conn, conn.cursor() as cur:
            cur.execute("SELECT u.id,p.id,o.id,i.id FROM users u JOIN products p ON p.created_by=u.id "
                        "JOIN orders o ON o.user_id=u.id JOIN order_items i ON i.order_id=o.id AND i.product_id=p.id")
            assert tuple(str(v) for v in cur.fetchone()) == (user_id, product_id, order_id, item_id)
    finally:
        with admin.cursor() as cur:
            cur.execute(sql.SQL("DROP DATABASE {} WITH (FORCE)").format(sql.Identifier(name)))
        admin.close()
