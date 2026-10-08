"""Transport selection only; the P0 assertions and expected defects stay unchanged."""
import os
import ssl

import httpx


def http_client(url, backend=False):
    options = {}
    if url.startswith('https://'):
        os.environ.pop('SSLKEYLOGFILE', None)
        context = ssl.create_default_context(cafile=os.environ['SERVER_CA' if backend else 'EDGE_CA'])
        context.hostname_checks_common_name = False
        if backend:
            context.load_cert_chain(os.environ['CLIENT_CERT'], os.environ['CLIENT_KEY'])
        options['verify'] = context
    return httpx.Client(base_url=url, timeout=10, **options)
