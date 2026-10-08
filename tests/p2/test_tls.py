"""Real socket handshakes against the deployed TLS listeners; no HTTP auth substitute."""
import os
from pathlib import Path
import socket
import ssl

import pytest
from cryptography import x509
from cryptography.hazmat.primitives import serialization
from cryptography.x509.oid import ExtendedKeyUsageOID
from transport import http_client

PKI = Path('/test-tls')


def request(cert='kong/client', hostname='backend', version=None):
    context = ssl.create_default_context(cafile=str(PKI / 'trust/server-ca.pem'))
    context.hostname_checks_common_name = False
    if version:
        context.minimum_version = context.maximum_version = version
    if cert:
        context.load_cert_chain(str(PKI / (cert + '.pem')), str(PKI / (cert + '.key')))
    with socket.create_connection(('backend', 8443), timeout=5) as raw:
        with context.wrap_socket(raw, server_hostname=hostname) as tls:
            tls.sendall(b'GET /health HTTP/1.1\r\nHost: backend\r\nConnection: close\r\n\r\n')
            return tls.recv(8192)


@pytest.mark.parametrize('version', [ssl.TLSVersion.TLSv1_2, ssl.TLSVersion.TLSv1_3])
def test_valid_mtls_is_http_200(version):
    assert request(version=version).startswith(b'HTTP/1.1 200')


@pytest.mark.parametrize('cert', [None, 'negative/untrusted', 'negative/expired',
                                 'negative/unenrolled', 'negative/wrong-client-eku'])
@pytest.mark.parametrize('version', [ssl.TLSVersion.TLSv1_2, ssl.TLSVersion.TLSv1_3])
def test_bad_client_is_tls_failure_not_http_auth(cert, version, record_property):
    try:
        data = request(cert, version=version)
    except (ssl.SSLError, ConnectionResetError) as exc:
        record_property('tls_rejection', type(exc).__name__ + ': ' + str(exc))
        print('TLS rejection:', cert or 'missing', version.name, type(exc).__name__, str(exc))
    else:
        assert data == b'', 'Rejected peer must never reach an HTTP handler'
        print('TLS rejection:', cert or 'missing', version.name, 'closed before HTTP')
        record_property('tls_rejection', 'closed before HTTP; no HTTP status')


def test_client_rejects_wrong_server_hostname():
    with pytest.raises(ssl.SSLCertVerificationError, match='Hostname mismatch'):
        request(hostname='other.internal')


@pytest.mark.parametrize('host,port', [('backend', 8443), ('backend', 8000), ('kong', 8000)])
def test_plain_http_cannot_reach_backend_or_gateway(host, port):
    try:
        with socket.create_connection((host, port), timeout=3) as value:
            value.sendall(b'GET /health HTTP/1.1\r\nHost: backend\r\n\r\n')
            data = value.recv(1024)
            assert not data.startswith(b'HTTP/'), 'A plaintext HTTP listener is available'
    except (ConnectionRefusedError, ConnectionResetError):
        pass


def test_https_gateway_health_and_http_401_are_distinct_from_tls_failure():
    with http_client(os.environ['GATEWAY_URL']) as client:
        assert client.get('/health').status_code == 200
        assert client.get('/health/ready').status_code == 200
        response = client.get('/api/v1/auth/me')
        assert response.status_code == 401 and 'kong' in response.headers['via'].lower()


@pytest.mark.parametrize('file,names,purpose', [
    ('backend/server.pem', ['backend'], ExtendedKeyUsageOID.SERVER_AUTH),
    ('kong/client.pem', ['kong.internal'], ExtendedKeyUsageOID.CLIENT_AUTH),
    ('backend/health.pem', ['backend-health.internal'], ExtendedKeyUsageOID.CLIENT_AUTH),
    ('kong/edge.pem', ['localhost', 'kong'], ExtendedKeyUsageOID.SERVER_AUTH),
])
def test_certificate_san_usage_and_leaf_constraints(file, names, purpose):
    cert = x509.load_pem_x509_certificate((PKI / file).read_bytes())
    assert cert.extensions.get_extension_for_class(x509.BasicConstraints).value.ca is False
    assert list(cert.extensions.get_extension_for_class(x509.ExtendedKeyUsage).value) == [purpose]
    assert set(cert.extensions.get_extension_for_class(x509.SubjectAlternativeName).value.get_values_for_type(x509.DNSName)) == set(names)
    assert cert.extensions.get_extension_for_class(x509.KeyUsage).value.digital_signature


def test_client_pin_store_enrolls_exactly_two_leaf_identities():
    pinned = x509.load_pem_x509_certificates((PKI / 'backend/client-pins.pem').read_bytes())
    assert len(pinned) == 2
    assert {c.public_bytes(serialization.Encoding.PEM)
            for c in pinned} == {(PKI / 'kong/client.pem').read_bytes(), (PKI / 'backend/health.pem').read_bytes()}
