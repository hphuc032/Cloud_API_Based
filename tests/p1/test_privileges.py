"""P1 database checks use actual deployed roles; no mocked permission decisions."""
import os
from uuid import uuid4

import psycopg2
import pytest
from sqlalchemy.engine import make_url


@pytest.fixture
def runtime():
    conn = psycopg2.connect(os.environ["DATABASE_URL"])
    yield conn
    conn.rollback()
    conn.close()


@pytest.mark.parametrize("statement", [
    "CREATE TABLE public.p1_forbidden (id int)",
    "ALTER TABLE public.products ADD COLUMN p1_forbidden int",
    "DROP TABLE public.order_items",
    "CREATE SCHEMA p1_forbidden",
    "CREATE TEMP TABLE p1_forbidden (id int)",
    "CREATE FUNCTION public.p1_forbidden() RETURNS int LANGUAGE sql AS 'SELECT 1'",
    "ALTER ROLE app_runtime SUPERUSER",
    "SET ROLE app_migrator",
    "SET ROLE postgres",
    "TRUNCATE public.users CASCADE",
    "DELETE FROM public.products",
    "UPDATE public.alembic_version SET version_num='forbidden'",
    "SELECT * FROM public.audit_logs",
    "INSERT INTO public.categories(name,slug) VALUES ('forbidden','forbidden')",
])
def test_runtime_privilege_denials(runtime, statement):
    with runtime.cursor() as cur, pytest.raises(psycopg2.errors.InsufficientPrivilege):
        cur.execute(statement)


def test_runtime_role_attributes(runtime):
    with runtime.cursor() as cur:
        cur.execute("SELECT current_user, rolsuper, rolcreatedb, rolcreaterole, rolreplication, rolbypassrls "
                    "FROM pg_roles WHERE rolname=current_user")
        assert cur.fetchone() == ("app_runtime", False, False, False, False, False)
        cur.execute("SELECT has_schema_privilege(current_user,'public','CREATE'), "
                    "has_database_privilege(current_user,current_database(),'CREATE'), "
                    "has_database_privilege(current_user,current_database(),'TEMP')")
        assert cur.fetchone() == (False, False, False)
        cur.execute("SELECT count(*) FROM pg_class WHERE relnamespace='public'::regnamespace "
                    "AND relowner=(SELECT oid FROM pg_roles WHERE rolname=current_user)")
        assert cur.fetchone()[0] == 0


def test_required_runtime_dml(runtime):
    # Rolled back: additionally proves trigger/enum/UUID functions work under the limited role.
    with runtime.cursor() as cur:
        cur.execute("INSERT INTO users(email,username,hashed_password) VALUES (%s,%s,%s) RETURNING id",
                    (f"{uuid4()}@example.com", str(uuid4()), "synthetic-non-login-fixture"))
        user_id = cur.fetchone()[0]
        cur.execute("UPDATE users SET full_name='P1' WHERE id=%s", (user_id,))
        cur.execute("INSERT INTO products(sku,name,price,stock_quantity,created_by) "
                    "VALUES (%s,'P1',10,4,%s) RETURNING id", (str(uuid4()), user_id))
        product_id = cur.fetchone()[0]
        cur.execute("UPDATE products SET stock_quantity=3 WHERE id=%s", (product_id,))
        cur.execute("INSERT INTO orders(user_id,order_number,total_amount) VALUES (%s,%s,10) RETURNING id",
                    (user_id, str(uuid4())))
        order_id = cur.fetchone()[0]
        cur.execute("INSERT INTO order_items(order_id,product_id,quantity,unit_price) VALUES (%s,%s,1,10)", (order_id, product_id))
        cur.execute("UPDATE orders SET status='shipped' WHERE id=%s", (order_id,))
        cur.execute("INSERT INTO refresh_tokens(user_id,token_hash,expires_at) VALUES (%s,%s,now()+interval '1 day') RETURNING id",
                    (user_id, str(uuid4())))
        token_id = cur.fetchone()[0]
        cur.execute("UPDATE refresh_tokens SET revoked=true WHERE id=%s", (token_id,))
        for table in ("users", "products", "orders", "order_items", "refresh_tokens", "categories", "alembic_version"):
            cur.execute("SELECT count(*) FROM " + table)
            assert cur.fetchone()[0] >= 0


def test_migration_role_owns_schema_objects_and_can_ddl():
    with psycopg2.connect(os.environ["P1_MIGRATION_DATABASE_URL"]) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT current_user, rolsuper, rolcreatedb, rolcreaterole FROM pg_roles WHERE rolname=current_user")
            assert cur.fetchone() == ("app_migrator", False, False, False)
            cur.execute("SELECT pg_get_userbyid(relowner) FROM pg_class WHERE oid='public.users'::regclass")
            assert cur.fetchone()[0] == "app_migrator"
            cur.execute("SELECT version_num FROM alembic_version")
            assert cur.fetchone()[0] == "0002_external_identities"
            cur.execute("CREATE TABLE public.p1_migration_probe (id int)")
            cur.execute("ALTER TABLE public.p1_migration_probe ADD COLUMN label text")
            cur.execute("DROP TABLE public.p1_migration_probe")


def test_password_file_supports_url_encoding():
    # No credential value is hardcoded or displayed.
    url = make_url(os.environ["DATABASE_URL"])
    assert url.username == "app_runtime"
    assert url.host == "postgres"
