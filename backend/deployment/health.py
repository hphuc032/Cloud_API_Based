"""Verified HTTPS/mTLS local readiness; a separate client key avoids copying Kong's key."""
import os
import ssl
import urllib.request


def context():
    os.environ.pop('SSLKEYLOGFILE', None)
    tls = os.environ.get('TLS_DIRECTORY', '/run/tls')
    value = ssl.create_default_context(cafile=tls + '/server-ca.pem')
    value.hostname_checks_common_name = False
    value.minimum_version = ssl.TLSVersion.TLSv1_2
    value.load_cert_chain(tls + '/health.pem', tls + '/health.key')
    return value


def status(path='/health/ready'):
    # Service DNS name has the single server SAN; no localhost SAN fallback.
    return urllib.request.urlopen('https://backend:8443' + path, context=context(), timeout=4).status


if __name__ == '__main__':
    status()
