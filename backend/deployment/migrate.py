"""Dedicated migration job; explicit runtime grants follow a successful upgrade."""
import os

import psycopg2
from psycopg2 import sql

from deployment.common import configure_application


def migrate():
    configure_application(migration=True)
    # Import only after configuring migration credentials.
    from alembic import command
    from alembic.config import Config
    command.upgrade(Config("alembic.ini"), "head")
    with psycopg2.connect(os.environ["DATABASE_URL"]) as conn:
        with conn.cursor() as cur:
            cur.execute("REVOKE ALL ON ALL TABLES IN SCHEMA public FROM app_runtime")
            cur.execute("REVOKE ALL ON ALL SEQUENCES IN SCHEMA public FROM app_runtime")
            for table in ("users", "products", "orders", "refresh_tokens"):
                cur.execute(sql.SQL("GRANT SELECT, INSERT, UPDATE ON public.{} TO app_runtime").format(sql.Identifier(table)))
            cur.execute("GRANT SELECT, INSERT ON public.order_items TO app_runtime")
            cur.execute("GRANT SELECT ON public.categories, public.alembic_version TO app_runtime")
            if os.environ.get("AUTH_MODE", "legacy") == "oidc":
                # P4 grants only identity lookup; runtime cannot provision or relink accounts.
                cur.execute("GRANT SELECT ON public.external_identities TO app_runtime")
            cur.execute("REVOKE EXECUTE ON FUNCTION public.update_updated_at_column() FROM PUBLIC")
            cur.execute("GRANT EXECUTE ON FUNCTION public.update_updated_at_column() TO app_runtime")
            # No blanket default grants: new tables need an explicit privilege review.
            cur.execute("ALTER DEFAULT PRIVILEGES IN SCHEMA public REVOKE EXECUTE ON FUNCTIONS FROM PUBLIC")
    print("Migrations and runtime grants completed")


if __name__ == "__main__":
    migrate()
