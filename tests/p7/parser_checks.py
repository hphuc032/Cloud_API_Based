"""Bounded real-mTLS checks of the deployed login form parser, before auth logic.

Only disposable test deployments. No credentials, tokens, request bodies or user
records are emitted. Normal input still reaches the unchanged auth decision.
"""
import io
import json
import os
from pathlib import Path
import sys
import unittest

from deployment.common import configure_application
configure_application()
from transport import http_client


class ParserChecks(unittest.TestCase):
    results = []

    def request(self, name, body, content_type, expected):
        with http_client('https://backend:8443', backend=True) as client:
            response = client.post('/api/v1/auth/login', content=body,
                                   headers={'Content-Type': content_type})
        self.results.append({'name':name, 'status':response.status_code,
                             'expected':expected, 'request_bytes':len(body)})
        self.assertEqual(response.status_code, expected)

    def test_normal_urlencoded_reaches_auth_policy(self):
        self.request('normal-urlencoded', b'username=parser-check%40example.invalid&password=invalid-password',
                     'application/x-www-form-urlencoded', 410 if os.environ.get('AUTH_MODE') == 'oidc' else 401)

    def test_urlencoded_field_count_is_bounded(self):
        self.request('urlencoded-field-count', '&'.join('k'+str(i)+'=v' for i in range(1001)).encode(),
                     'application/x-www-form-urlencoded', 400)

    def test_urlencoded_field_size_is_bounded(self):
        self.request('urlencoded-field-size', b'payload='+b'x'*(1024*1024+1),
                     'application/x-www-form-urlencoded', 400)

    def test_multipart_text_field_is_bounded(self):
        self.request('multipart-text-size', b'--boundary\r\nContent-Disposition: form-data; name="payload"\r\n\r\n'+
                     b'x'*(1024*1024+1)+b'\r\n--boundary--\r\n', 'multipart/form-data; boundary=boundary', 400)

    def test_multipart_header_size_is_bounded(self):
        self.request('multipart-header-size', b'--boundary\r\nContent-Disposition: form-data; name="payload"\r\nX-Part: '+
                     b'x'*65536+b'\r\n\r\nx\r\n--boundary--\r\n', 'multipart/form-data; boundary=boundary', 400)


if __name__ == '__main__':
    if os.environ.get('APP_ENV') != 'test' or os.environ.get('P0_ISOLATED') != '1':
        raise SystemExit('Disposable test environment required')
    buffer=io.StringIO()
    result=unittest.TextTestRunner(stream=buffer,verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(ParserChecks))
    print(buffer.getvalue())
    Path('/results/parser-boundary-results.json').write_text(json.dumps({
        'tests':result.testsRun,'failures':len(result.failures),'errors':len(result.errors),'cases':ParserChecks.results},indent=2))
    raise SystemExit(0 if result.wasSuccessful() else 1)
