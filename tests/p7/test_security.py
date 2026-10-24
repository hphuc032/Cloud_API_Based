"""P7 lab scenarios: real Kong HTTPS, enrolled backend mTLS and Keycloak tokens.

Negative signed tokens are only attack fixtures; positive requests use genuine
Keycloak Authorization Code + S256 token fixtures. Credentials never enter evidence.
"""
import json
import os
from pathlib import Path
from uuid import uuid4

import psycopg2
import pytest
from test_cutover import client, backend, headers, tokens, identity, admin, legacy_order, signed as alter_token
from test_hardening import envelope, raw, signed, receipt
from test_observability import ingested


def record(scenario, steps, **checks):
    path = Path('/results/p7-scenarios.json')
    data = json.loads(path.read_text()) if path.exists() else []
    data.append({'scenario': scenario, 'status': 'PASS', 'steps': steps, 'checks': checks})
    path.write_text(json.dumps(data, indent=2))


def observed(response, method, path, expected, event=None, service='backend'):
    assert response.status_code == expected
    rid = response.headers.get('x-request-id')
    if event:
        assert rid
        ingested(service, event, rid)
    return {'method': method, 'path': path, 'expected': expected, 'actual': response.status_code,
            'request_id': rid, 'observed_event': event, 'event_service': service if event else None}


def test_as01_missing_token(client):
    path = '/api/v1/auth/me'
    r = client.get(path)
    step = observed(r, 'GET', path, 401, 'token_rejected', 'kong')
    assert 'x-kong-upstream-latency' not in r.headers
    record('AS01', [step], rejected_before_upstream=True)


def test_as02_invalid_signature(client, tokens):
    # Changing the signature to invalid bytes preserves the actual kid/claims.
    t = tokens['customer']['access_token'].rsplit('.', 1)[0] + '.' + 'A' * 342
    r = client.get('/api/v1/auth/me', headers={'Authorization': 'Bearer ' + t})
    step = observed(r, 'GET', '/api/v1/auth/me', 401, 'token_rejected', 'kong')
    assert 'x-kong-upstream-latency' not in r.headers
    record('AS02', [step], no_legacy_fallback=True)


@pytest.mark.parametrize('change', [{'aud': 'wrong'}, {'iss': 'https://untrusted.example/realms/x'}])
def test_as03_gateway_is_not_complete_oidc(client, backend, headers, tokens, change):
    headers('customer')
    h = {'Authorization': 'Bearer ' + alter_token(tokens['customer']['access_token'], change)}
    r = client.get('/api/v1/auth/me', headers=h)
    step = observed(r, 'GET', '/api/v1/auth/me', 401, 'token_rejected')
    assert 'x-kong-upstream-latency' in r.headers
    assert backend.get('/api/v1/auth/me', headers=h).status_code == 401
    record('AS03', [step], altered_claim=list(change), backend_independently_rejected=True)


def test_as04_customer_cannot_mutate_admin(client, headers, users):
    path = '/api/v1/users/' + str(users['customer_b'].id)
    r = client.patch(path, headers=headers('customer'), json={'role': 'admin'})
    step = observed(r, 'PATCH', '/api/v1/users/<other-user>', 403, 'rbac_denied')
    with psycopg2.connect(os.environ['P0_ADMIN_DATABASE_URL']) as conn, conn.cursor() as cur:
        cur.execute('SELECT role FROM users WHERE id=%s', (str(users['customer_b'].id),))
        assert cur.fetchone()[0] == 'customer'
    record('AS04', [step], no_role_mutation=True)


def test_as05_bola(client, headers, legacy_order):
    r = client.get('/api/v1/orders/' + legacy_order, headers=headers('customer_b'))
    step = observed(r, 'GET', '/api/v1/orders/<other-order>', 403, 'ownership_denied')
    assert 'items' not in r.json() and 'user_id' not in r.json()
    record('AS05', [step], no_order_disclosure=True)


def test_as06_forgery_no_receipt(client):
    payload = envelope(); body = raw(payload)
    r = client.post('/api/v1/webhooks/receive', content=body,
                    headers={**signed(body), 'X-Signature': 'sha256=' + '0' * 64})
    step = observed(r, 'POST', '/api/v1/webhooks/receive', 403, 'webhook_rejected')
    assert receipt(payload['event_id']) == []
    record('AS06', [step], receipt_count=0)


def test_as07_network_replay_and_conflict(client):
    obj = envelope(); body = raw(obj); path = '/api/v1/webhooks/receive'
    first = client.post(path, content=body, headers=signed(body))
    second = client.post(path, content=body, headers=signed(body))
    assert first.status_code == second.status_code == 200 and first.json() == second.json()
    assert first.headers['x-webhook-replayed'] == 'false' and second.headers['x-webhook-replayed'] == 'true'
    steps = [observed(second, 'POST', path, 200, 'webhook_replayed')]
    conflict = raw(dict(obj, order_id='different'))
    r = client.post(path, content=conflict, headers=signed(conflict))
    steps.append(observed(r, 'POST', path, 409, 'webhook_conflict'))
    assert len(receipt(obj['event_id'])) == 1
    record('AS07', steps, durable_receipts=1, first_replayed=False, retry_replayed=True,
           concurrency_evidence='P5 test_concurrent_duplicates_real_postgres; no real payment handler')


@pytest.mark.parametrize('destination', ['127.0.0.1', '[::1]', '[::ffff:127.0.0.1]', '10.0.0.1', '172.16.0.1', '192.168.0.1', '169.254.1.1', '169.254.169.254'])
def test_as08_validator_denies_nonpublic(client, headers, destination):
    path = '/api/v1/security/fetch-url'
    r = client.post(path, headers=headers('staff'), json={'url': 'http://' + destination})
    step = observed(r, 'POST', path, 403, 'ssrf_denied')
    record('AS08', [step], destination=destination, validates_only_no_outbound_fetch=True)


@pytest.mark.parametrize('payload', ["' OR '1'='1", "x'); SELECT 1; --"])
def test_as10_sql_shaped_uuid_no_business_effect(client, headers, users, payload):
    r = client.get('/api/v1/users/' + payload, headers=headers('admin'))
    step = observed(r, 'GET', '/api/v1/users/<sql-shaped-id>', 422, 'validation_failed')
    with psycopg2.connect(os.environ['P0_ADMIN_DATABASE_URL']) as conn, conn.cursor() as cur:
        cur.execute('SELECT count(*) FROM users'); assert cur.fetchone()[0] == 4
    record('AS10', [step], fixture_user_count=4, scope='UUID input validation; not exhaustive injection certification')


@pytest.mark.parametrize('kind', ['price', 'role', 'uuid', 'json'])
def test_as11_input_no_unhandled_500(client, headers, users, product, kind):
    if kind == 'price':
        path = '/api/v1/products/' + str(product.id)
        r = client.patch(path, headers=headers('staff'), json={'price': None}); expected = 422
    elif kind == 'role':
        path = '/api/v1/users/' + str(users['customer'].id)
        r = client.patch(path, headers=headers('admin'), json={'role': None}); expected = 422
    elif kind == 'uuid':
        path = '/api/v1/orders/not-a-uuid'
        r = client.get(path, headers=headers('customer')); expected = 422
    else:
        path = '/api/v1/webhooks/receive'; body = b'{'
        r = client.post(path, content=body, headers=signed(body)); expected = 400
    step = observed(r, r.request.method, '/api/v1/<validated-resource>', expected)
    with psycopg2.connect(os.environ['P0_ADMIN_DATABASE_URL']) as conn, conn.cursor() as cur:
        cur.execute('SELECT role FROM users WHERE id=%s', (str(users['customer'].id),)); assert cur.fetchone()[0] == 'customer'
        cur.execute('SELECT price FROM products WHERE id=%s', (str(product.id),)); assert float(cur.fetchone()[0]) == 12.5
        cur.execute('SELECT count(*) FROM webhook_receipts'); assert cur.fetchone()[0] == 0
    record('AS11', [step], input=kind, no_partial_mutation=True)


def test_recovery_seed_real_oidc_chain(client, headers, users, product):
    """Last test deliberately leaves synthetic linked data for paired recovery."""
    steps = []
    for role in ('customer', 'customer_b', 'staff', 'admin'):
        r = client.get('/api/v1/auth/me', headers=headers(role))
        steps.append(observed(r, 'GET', '/api/v1/auth/me', 200))
        assert r.json()['id'] == str(users[role].id)
    for role in ('customer', 'customer_b'):
        r = client.post('/api/v1/orders/', headers=headers(role), json={'items': [{'product_id': str(product.id), 'quantity': 1}]})
        steps.append(observed(r, 'POST', '/api/v1/orders/', 201, 'http_request'))
        with psycopg2.connect(os.environ['P0_ADMIN_DATABASE_URL']) as conn, conn.cursor() as cur:
            cur.execute('SELECT user_id FROM orders WHERE id=%s', (r.json()['id'],))
            assert str(cur.fetchone()[0]) == str(users[role].id)
    body = raw(envelope())
    assert client.post('/api/v1/webhooks/receive', content=body, headers=signed(body)).status_code == 200
    record('E2E-RECOVERY-SEED', steps, four_reviewed_mappings=True, synthetic_orders=2,
           synthetic_receipts=1, positive_tokens='actual Keycloak code+PKCE S256')
