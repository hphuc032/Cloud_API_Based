"""Idempotent privileged provisioning; no row changes or initial migration rewrites."""
import os

import psycopg2
from psycopg2 import sql

from deployment.common import TABLES, database_url, secret


def bootstrap():
    with psycopg2.connect(database_url("postgres", secret("POSTGRES_PASSWORD_FILE"))) as conn:
        with conn.cursor() as cur:
            for role, password_file in (("app_migrator", "MIGRATION_PASSWORD_FILE"),
                                        ("app_runtime", "RUNTIME_PASSWORD_FILE")):
                cur.execute("SELECT 1 FROM pg_roles WHERE rolname=%s", (role,))
                if not cur.fetchone():
                    cur.execute(sql.SQL("CREATE ROLE {} LOGIN").format(sql.Identifier(role)))
                cur.execute(sql.SQL("ALTER ROLE {} WITH LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE "
                                    "NOREPLICATION NOBYPASSRLS NOINHERIT PASSWORD {}").format(
                                        sql.Identifier(role), sql.Literal(secret(password_file))))
                # A pre-existing role membership could circumvent explicit grants.
                cur.execute("SELECT parent.rolname FROM pg_auth_members m JOIN pg_roles parent "
                            "ON parent.oid=m.roleid JOIN pg_roles child ON child.oid=m.member "
                            "WHERE child.rolname=%s", (role,))
                if cur.fetchall():
                    raise RuntimeError(f"Unexpected memberships for {role}; manual review required")
            db = sql.Identifier(os.environ.get("APP_DB_NAME", "appdb"))
            cur.execute(sql.SQL("REVOKE ALL ON DATABASE {} FROM PUBLIC, app_runtime, app_migrator").format(db))
            cur.execute(sql.SQL("GRANT CONNECT ON DATABASE {} TO app_runtime, app_migrator").format(db))
            cur.execute("REVOKE ALL ON SCHEMA public FROM PUBLIC, app_runtime, app_migrator")
            cur.execute("GRANT USAGE, CREATE ON SCHEMA public TO app_migrator")
            cur.execute("GRANT USAGE ON SCHEMA public TO app_runtime")
            cur.execute('CREATE EXTENSION IF NOT EXISTS "uuid-ossp"')
            # Transfer only known application objects, never REASSIGN OWNED BY postgres.
            for table in TABLES:
                cur.execute("SELECT pg_get_userbyid(relowner) FROM pg_class "
                            "WHERE oid=to_regclass(%s)", ("public." + table,))
                owner = cur.fetchone()
                if owner:
                    if owner[0] not in ("postgres", "app_migrator"):
                        raise RuntimeError("Unexpected application object owner; manual review required")
                    cur.execute(sql.SQL("ALTER TABLE public.{} OWNER TO app_migrator").format(sql.Identifier(table)))
            for typename in ("userrole", "orderstatus"):
                cur.execute("SELECT 1 FROM pg_type WHERE typnamespace='public'::regnamespace AND typname=%s", (typename,))
                if cur.fetchone():
                    cur.execute(sql.SQL("ALTER TYPE public.{} OWNER TO app_migrator").format(sql.Identifier(typename)))
            cur.execute("SELECT to_regprocedure('public.update_updated_at_column()')")
            if cur.fetchone()[0]:
                cur.execute("ALTER FUNCTION public.update_updated_at_column() OWNER TO app_migrator")
    print("Database bootstrap completed")


if __name__ == "__main__":
    bootstrap()
