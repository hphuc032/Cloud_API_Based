import os
from pathlib import Path
import shutil
import subprocess
from urllib.parse import urlparse, urlunparse
from uuid import uuid4

import psycopg2
from psycopg2 import sql
import pytest

TABLES = ["users", "refresh_tokens", "categories", "products", "orders", "order_items", "audit_logs"]


@pytest.fixture
def isolated_database():
    parsed = urlparse(os.environ["DATABASE_URL"])
    name = "p0_verify_" + uuid4().hex
    admin = psycopg2.connect(os.environ["DATABASE_URL"])
    admin.autocommit = True
    with admin.cursor() as cur:
        cur.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
    test_url = urlunparse(parsed._replace(path="/" + name))
    try:
        yield name, test_url
    finally:
        with admin.cursor() as cur:
            cur.execute(sql.SQL("DROP DATABASE {} WITH (FORCE)").format(sql.Identifier(name)))
        admin.close()


def alembic(url, *args, cwd="/app"):
    env = dict(os.environ, DATABASE_URL=url)
    proc = subprocess.run(["alembic", *args], cwd=cwd, env=env,
                          capture_output=True, text=True)
    # Omit command environment and potentially sensitive SQL values on failure.
    assert proc.returncode == 0, "Alembic command failed: " + " ".join(args)


def test_clean_database_migrations_and_downgrade(isolated_database):
    _, url = isolated_database
    with psycopg2.connect(url) as conn, conn.cursor() as cur:
        cur.execute("SELECT tablename FROM pg_tables WHERE schemaname='public'")
        assert cur.fetchall() == []
    alembic(url, "upgrade", "head")
    # Idempotence, revision stamp, all tables, FK constraints and trigger installation.
    alembic(url, "upgrade", "head")
    with psycopg2.connect(url) as conn, conn.cursor() as cur:
        cur.execute("SELECT version_num FROM alembic_version")
        assert cur.fetchone()[0] == "0001_initial_schema"
        cur.execute("SELECT tablename FROM pg_tables WHERE schemaname='public'")
        assert {row[0] for row in cur.fetchall()} == set(TABLES + ["alembic_version"])
        cur.execute("SELECT count(*) FROM pg_constraint WHERE contype='f' AND connamespace='public'::regnamespace")
        assert cur.fetchone()[0] == 7
        cur.execute("SELECT count(*) FROM information_schema.triggers WHERE trigger_schema='public'")
        assert cur.fetchone()[0] == 4
        cur.execute("SELECT enumlabel FROM pg_enum JOIN pg_type ON pg_type.oid=enumtypid WHERE typname='userrole'")
        assert {row[0] for row in cur.fetchall()} == {"customer", "staff", "admin"}
    alembic(url, "downgrade", "base")
    with psycopg2.connect(url) as conn, conn.cursor() as cur:
        cur.execute("SELECT tablename FROM pg_tables WHERE schemaname='public'")
        assert {row[0] for row in cur.fetchall()} == {"alembic_version"}
    alembic(url, "upgrade", "head")


def test_migration_template_generates_executable_revision(tmp_path, isolated_database):
    _, url = isolated_database
    shutil.copytree("/app/alembic", tmp_path / "alembic")
    shutil.copy("/app/alembic.ini", tmp_path / "alembic.ini")
    alembic(url, "revision", "-m", "p0 template probe", "--rev-id", "p0_template_probe", cwd=tmp_path)
    generated = list((tmp_path / "alembic/versions").glob("p0_template_probe_*.py"))
    assert len(generated) == 1
    source = generated[0].read_text()
    compile(source, str(generated[0]), "exec")
    assert "def upgrade()" in source and "def downgrade()" in source
    alembic(url, "upgrade", "head", cwd=tmp_path)
    with psycopg2.connect(url) as conn, conn.cursor() as cur:
        cur.execute("SELECT version_num FROM alembic_version")
        assert cur.fetchone()[0] == "p0_template_probe"
    alembic(url, "downgrade", "base", cwd=tmp_path)


def snapshot(url):
    with psycopg2.connect(url) as conn, conn.cursor() as cur:
        result = {}
        for table in TABLES + ["alembic_version"]:
            cur.execute(sql.SQL("SELECT row_to_json(t)::text FROM {} t ORDER BY row_to_json(t)::text").format(sql.Identifier(table)))
            result[table] = cur.fetchall()
        return result


def test_pg_dump_restore_preserves_ids_relationships_and_data(isolated_database, tmp_path, orders, login):
    login()  # Include hashed refresh-token data as well as users/products/orders/items.
    name, restored_url = isolated_database
    parsed = urlparse(os.environ["DATABASE_URL"])
    env = dict(os.environ, PGPASSWORD=parsed.password)
    archive = tmp_path / "p0.dump"
    common = ["-h", "postgres", "-U", "postgres"]
    before = snapshot(os.environ["DATABASE_URL"])
    for command in (["pg_dump", *common, "-d", "p0_baseline", "-Fc", "-f", str(archive)],
                    ["pg_restore", *common, "-d", name, "--exit-on-error", str(archive)]):
        proc = subprocess.run(command, env=env, capture_output=True, text=True)
        assert proc.returncode == 0, command[0] + " failed"
    assert snapshot(restored_url) == before
    with psycopg2.connect(restored_url) as conn, conn.cursor() as cur:
        cur.execute("SELECT count(*) FROM orders o JOIN users u ON u.id=o.user_id "
                    "JOIN order_items i ON i.order_id=o.id JOIN products p ON p.id=i.product_id")
        assert cur.fetchone()[0] == 2
        cur.execute("SELECT count(*) FROM pg_constraint WHERE contype='f' AND connamespace='public'::regnamespace")
        assert cur.fetchone()[0] == 7
    # Restored database is accepted by migration tooling without recreating data.
    alembic(restored_url, "upgrade", "head")
    assert snapshot(restored_url) == before
