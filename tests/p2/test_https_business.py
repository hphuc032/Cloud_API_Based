"""Re-use P0 policy assertions through Kong HTTPS + upstream mTLS, not TestClient."""
import os
import time

import pytest
from transport import http_client
from test_authorization import (
    test_product_crud_authorization as test_https_product_crud_authorization,
    test_order_create_authorization_and_server_ownership as test_https_order_create,
    test_order_list_read_status_authorization as test_https_order_list_read_status,
    test_user_self_vs_admin_authorization as test_https_user_access,
    test_admin_self_protection_and_db_role_active_authority as test_https_db_authority,
    test_invalid_orders_do_not_deduct_stock as test_https_invalid_orders,
    test_current_order_status_policy as test_https_order_status_policy,
    test_defect_product_null_field as test_https_defect_product_null,
    test_defect_user_null_field as test_https_defect_user_null,
)
from test_auth import (
    test_rejected_access_tokens as test_https_bad_jwt,
    test_current_login_claims_and_refresh_hash as test_https_login,
    test_refresh_rotation_and_reuse as test_https_refresh_rotation,
    test_refresh_rejection as test_https_refresh_rejection,
    test_logout_revokes_only_owned_refresh_and_keeps_access as test_https_logout,
    test_registration_cannot_assign_admin as test_https_registration,
    test_login_lockout as test_https_login_lockout,
    test_defect_jwt_requires_exp as test_https_defect_exp,
    test_defect_malformed_subject_is_401 as test_https_defect_sub,
)
from test_webhook_ssrf import (
    test_webhook_hmac_timestamp as test_https_webhook,
    test_webhook_debug_helper_disabled as test_https_debug_helper,
    test_defect_webhook_json_shape as test_https_defect_webhook_shape,
    test_defect_webhook_replay as test_https_defect_webhook_replay,
)

# These business checks honor the unchanged 60/minute IP limiter. The separate
# P0 gateway test deliberately exhausts it and asserts 429; no limiter is disabled.
_wait_until = 0
_next_send = 0


class PacedClient:
    def __init__(self, client):
        self.client = client

    def __getattr__(self, method):
        def send(*args, **kwargs):
            global _wait_until, _next_send
            if time.time() < _wait_until:
                time.sleep(_wait_until - time.time())
            # Leave headroom for the TLS smoke probes and Kong's log-phase counter
            # updates. Timing is test tooling only; production remains 60/minute.
            if time.monotonic() < _next_send:
                time.sleep(_next_send - time.monotonic())
            response = getattr(self.client, method)(*args, **kwargs)
            _next_send = time.monotonic() + 1.1
            assert response.status_code != 429 or method == 'post' and args[0] == '/api/v1/auth/login', 'Unexpected gateway rate limit'
            if int(response.headers.get('x-ratelimit-remaining-minute', '60')) <= 3:
                _wait_until = (int(time.time()) // 60 + 1) * 60 + 2
            return response
        return send


@pytest.fixture
def client():
    with http_client(os.environ['GATEWAY_URL']) as value:
        yield PacedClient(value)


@pytest.mark.parametrize('role,expected', [('anonymous', 401), ('customer', 403), ('staff', 200), ('admin', 200)])
def test_https_ssrf_uses_real_dns_and_preserves_roles(client, headers, role, expected):
    assert client.post('/api/v1/security/fetch-url', headers=headers(role),
                       json={'url': 'https://example.com/test'}).status_code == expected


@pytest.mark.parametrize('url,expected', [('http://169.254.169.254', 403), ('http://localhost', 403),
                                        ('https://example.com.evil.test', 403), ('ftp://example.com/file', 422)])
def test_https_ssrf_denies_invalid_targets(client, headers, url, expected):
    assert client.post('/api/v1/security/fetch-url', headers=headers('staff'), json={'url': url}).status_code == expected
