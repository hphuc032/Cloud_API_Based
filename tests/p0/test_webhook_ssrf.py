from datetime import datetime, timezone
import hashlib
import hmac
import socket

import pytest
from app.config import settings
from app.routes import security, webhooks
from baseline import KnownBaselineDefect, expected_status

BODY = b'{"event":"payment.success","order_id":"p0-order"}'


def signed(body=BODY, timestamp=None):
    ts = str(timestamp if timestamp is not None else int(datetime.now(timezone.utc).timestamp()))
    digest = hmac.new(settings.WEBHOOK_SECRET.encode(), ts.encode() + b"." + body,
                      hashlib.sha256).hexdigest()
    return {"X-Timestamp": ts, "X-Signature": "sha256=" + digest,
            "Content-Type": "application/json"}


@pytest.mark.parametrize("case,expected", [
    ("valid", 200), ("missing_timestamp", 401), ("bad_timestamp", 403),
    ("old", 403), ("future", 403), ("missing_signature", 401),
    ("wrong_signature", 403), ("wrong_prefix", 403), ("tampered_body", 403),
    ("tampered_timestamp", 403), ("invalid_json", 400),
])
def test_webhook_hmac_timestamp(client, case, expected):
    body = BODY
    now = int(datetime.now(timezone.utc).timestamp())
    auth = signed()
    if case == "missing_timestamp":
        del auth["X-Timestamp"]
    elif case == "bad_timestamp":
        auth["X-Timestamp"] = "invalid"
    elif case in ("old", "future"):
        auth = signed(timestamp=now + (-600 if case == "old" else 600))
    elif case == "missing_signature":
        del auth["X-Signature"]
    elif case == "wrong_signature":
        auth["X-Signature"] = "sha256=" + "0" * 64
    elif case == "wrong_prefix":
        auth["X-Signature"] = auth["X-Signature"].replace("sha256=", "sha1=")
    elif case == "tampered_body":
        body += b" "
    elif case == "tampered_timestamp":
        auth["X-Timestamp"] = str(now - 1)
    elif case == "invalid_json":
        body = b"{"
        auth = signed(body)
    response = client.post("/api/v1/webhooks/receive", headers=auth, content=body)
    assert response.status_code == expected
    if expected == 200:
        assert response.json()["received"] is True
        assert response.json()["event"] == "payment.success"


@pytest.mark.parametrize("offset,expected", [(-301, 403), (-300, 200), (300, 200), (301, 403)])
def test_webhook_exact_timestamp_boundary(client, monkeypatch, offset, expected):
    fixed = datetime(2026, 1, 1, tzinfo=timezone.utc)
    class Clock:
        @staticmethod
        def now(tz):
            return fixed
    monkeypatch.setattr(webhooks, "datetime", Clock)
    auth = signed(timestamp=int(fixed.timestamp()) + offset)
    assert client.post("/api/v1/webhooks/receive", headers=auth, content=BODY).status_code == expected


def test_webhook_debug_helper_disabled(client):
    assert client.get("/api/v1/webhooks/test-signature").status_code == 404


@pytest.mark.defect
def test_defect_webhook_json_shape(client):
    body = b"[]"
    response = client.post("/api/v1/webhooks/receive", headers=signed(body), content=body)
    assert response.status_code == 400


@pytest.mark.defect
def test_defect_webhook_replay(client):
    auth = signed()
    first = client.post("/api/v1/webhooks/receive", headers=auth, content=BODY)
    assert first.status_code == 200
    second = client.post("/api/v1/webhooks/receive", headers=auth, content=BODY)
    # P5 preserves the provider retry contract: stored acknowledgement, no effect.
    assert second.status_code == 200
    assert first.json() == second.json()
    assert first.headers['x-webhook-replayed'] == 'false'
    assert second.headers['x-webhook-replayed'] == 'true'


def dns_result(ips):
    return [(socket.AF_INET6 if ":" in ip else socket.AF_INET,
             socket.SOCK_STREAM, 6, "", (ip, 0)) for ip in ips]


@pytest.mark.parametrize("role,expected", [("anonymous", 401), ("customer", 403), ("staff", 200), ("admin", 200)])
def test_ssrf_role_access(client, headers, monkeypatch, role, expected):
    monkeypatch.setattr(security.socket, "getaddrinfo", lambda *a: dns_result(["93.184.216.34"]))
    assert client.post("/api/v1/security/fetch-url", headers=headers(role),
                       json={"url": "https://example.com/test"}).status_code == expected


@pytest.mark.parametrize("url,ips,expected", [
    ("https://example.com", ["93.184.216.34"], 200),
    ("https://sub.example.com", ["93.184.216.34"], 200),
    ("https://example.com.evil.test", ["93.184.216.34"], 403),
    ("https://evilexample.com", ["93.184.216.34"], 403),
    ("http://localhost", ["127.0.0.1"], 403),
    ("http://169.254.169.254", ["169.254.169.254"], 403),
    ("ftp://example.com/file", ["93.184.216.34"], 422),
    ("https://example.com", [], 400),
    *[("https://example.com", [ip], 403) for ip in [
        "127.0.0.1", "10.1.2.3", "172.16.0.1", "192.168.1.1", "169.254.169.254",
        "0.0.0.1", "::1", "fc00::1", "fe80::1"]],
    ("https://example.com", ["93.184.216.34", "10.0.0.1"], 403),
])
def test_ssrf_url_validation(client, headers, monkeypatch, url, ips, expected):
    monkeypatch.setattr(security.socket, "getaddrinfo", lambda *a: dns_result(ips))
    response = client.post("/api/v1/security/fetch-url", headers=headers("staff"), json={"url": url})
    assert response.status_code == expected
    if expected == 200:
        assert set(response.json()["resolved_ips"]) == set(ips)


def test_ssrf_dns_failure(client, headers, monkeypatch):
    def fail(*args):
        raise socket.gaierror("P0 simulated DNS failure")
    monkeypatch.setattr(security.socket, "getaddrinfo", fail)
    assert client.post("/api/v1/security/fetch-url", headers=headers("staff"),
                       json={"url": "https://example.com"}).status_code == 400


@pytest.mark.defect
def test_defect_ssrf_ipv4_mapped_loopback(client, headers, monkeypatch):
    monkeypatch.setattr(security.socket, "getaddrinfo", lambda *a: dns_result(["::ffff:127.0.0.1"]))
    response = client.post("/api/v1/security/fetch-url", headers=headers("staff"),
                           json={"url": "https://example.com"})
    assert response.status_code == 403
