"""Compose-only deployment helpers. Direct DATABASE_URL usage remains supported."""
import os
from pathlib import Path
import secrets

from sqlalchemy.engine import URL


def secret(name):
    value = Path(os.environ[name]).read_text(encoding="utf-8").strip()
    if not value:
        raise RuntimeError(f"Empty secret file: {name}")
    return value


def database_url(user, password):
    return URL.create("postgresql", username=user, password=password,
                      host=os.environ.get("DB_HOST", "postgres"), port=5432,
                      database=os.environ.get("APP_DB_NAME", "appdb")).render_as_string(hide_password=False)


def configure_application(migration=False):
    os.environ["DATABASE_URL"] = database_url(
        "app_migrator" if migration else "app_runtime", secret("DB_PASSWORD_FILE"))
    # Alembic imports Settings/models but never issues JWTs or handles webhooks.
    # Do not give the migration job the real application signing secrets.
    for name in ("SECRET_KEY", "WEBHOOK_SECRET"):
        os.environ[name] = secrets.token_hex(32) if migration else secret(name + "_FILE")


TABLES = ("users", "refresh_tokens", "categories", "products", "orders", "order_items", "audit_logs", "alembic_version")
