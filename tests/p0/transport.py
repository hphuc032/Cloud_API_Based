"""Transport selection only; the P0 assertions and expected defects stay unchanged."""
import os
import ssl
import time

import httpx


def wait_for_rate_limit_window(evidence=None):
    """Wait for an observed new wall-clock bucket, bounded by monotonic time."""
    boundary=(int(time.time())//60+1)*60+1
    deadline=time.monotonic()+90
    if evidence is not None:
        evidence.append({'event':'wait-start','wall_time':time.time(),
                         'monotonic':time.monotonic(),'boundary':boundary})
    while time.time()<boundary:
        assert time.monotonic()<deadline, 'Wall-clock rate-limit window did not advance within 90s'
        time.sleep(min(.25,max(0,boundary-time.time())))
    if evidence is not None:
        evidence.append({'event':'wait-end','wall_time':time.time(),
                         'monotonic':time.monotonic(),'boundary':boundary})


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
