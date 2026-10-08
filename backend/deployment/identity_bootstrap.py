"""Initialize a least-privilege Keycloak owner in the separate identity database."""
import psycopg2
from psycopg2 import sql
from deployment.common import secret

if __name__ == '__main__':
    with psycopg2.connect(host='identity-db',dbname='keycloak',user='postgres',
                          password=secret('IDENTITY_ADMIN_PASSWORD_FILE')) as conn,conn.cursor() as cur:
        cur.execute("SELECT 1 FROM pg_roles WHERE rolname='keycloak'")
        if not cur.fetchone():cur.execute('CREATE ROLE keycloak LOGIN')
        cur.execute(sql.SQL('ALTER ROLE keycloak NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS NOINHERIT PASSWORD {}').format(sql.Literal(secret('IDENTITY_DB_PASSWORD_FILE'))))
        cur.execute("SELECT 1 FROM pg_auth_members WHERE member=(SELECT oid FROM pg_roles WHERE rolname='keycloak')")
        if cur.fetchone():raise RuntimeError('Unexpected identity database role memberships')
        cur.execute('REVOKE ALL ON DATABASE keycloak FROM PUBLIC')
        cur.execute('ALTER DATABASE keycloak OWNER TO keycloak')
        cur.execute('REVOKE ALL ON SCHEMA public FROM PUBLIC')
        cur.execute('GRANT USAGE, CREATE ON SCHEMA public TO keycloak')
    print('Identity database owner provisioned')
