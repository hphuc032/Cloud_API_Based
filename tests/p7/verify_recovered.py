"""Read-only authenticated assertions after recovery, without destructive fixtures."""
import json
import os
import sys
import time
from pathlib import Path
sys.path[:0] = ['/tests/p0', '/tests/p2', '/tests/p3']
from deployment.common import configure_application, database_url
configure_application()
from test_identity import authorize, exchange
from transport import http_client
from test_https_business import PacedClient
import httpx
import psycopg2

fixture = json.loads(Path('/test-fixtures/identities.json').read_text())
admin_url = database_url('postgres', Path('/run/secrets/postgres_password').read_text().strip())
with psycopg2.connect(admin_url) as conn, conn.cursor() as cur:
    cur.execute('SELECT e.subject,u.id,u.role,u.is_active FROM external_identities e JOIN users u ON u.id=e.user_id')
    mapped = {r[0]: (str(r[1]), r[2], r[3]) for r in cur.fetchall()}
    cur.execute('SELECT id,user_id FROM orders'); orders = [(str(o), str(u)) for o, u in cur.fetchall()]
    assert len(mapped) == 4 and len(orders) == 2
with httpx.Client(verify='/identity-trust/identity-ca.pem', timeout=20, follow_redirects=False, trust_env=False) as identity, http_client('https://kong:8443') as wire:
    # Allow ordinary gateway DNS convergence after backend recreation, without
    # changing resolver TTLs, certificate validation or limiter policy.
    for _ in range(30):
        if wire.get('/health/ready').status_code == 200:
            break
        time.sleep(3)
    else:
        raise AssertionError('Recovered gateway readiness did not converge')
    api = PacedClient(wire)
    for role, user in fixture['users'].items():
        code, verifier, nonce = authorize(identity, user['username'], user['password'])
        result = exchange(identity, code, verifier); assert result.status_code == 200
        h = {'Authorization': 'Bearer ' + result.json()['access_token']}
        r = api.get('/api/v1/auth/me', headers=h); assert r.status_code == 200
        uid, expected_role, active = mapped[user['subject']]
        assert r.json()['id'] == uid and r.json()['role'] == expected_role and active
        r = api.get('/api/v1/users/', headers=h)
        assert r.status_code == (200 if role == 'admin' else 403)
        for order, owner in orders:
            r = api.get('/api/v1/orders/' + order, headers=h)
            assert r.status_code == (200 if role in ('staff', 'admin') or owner == uid else 403)
print('Recovered real PKCE -> Kong HTTPS -> backend mTLS -> PostgreSQL: four stable IDs/current roles, two owned orders; no privilege escalation')
