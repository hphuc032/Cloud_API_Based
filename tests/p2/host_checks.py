"""Fail-closed Kong tests, isolated rotation/recovery, runtime file and log evidence."""
import io
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import ssl
import socket
import subprocess
import time
import unittest
import urllib.request


def execute(run, compose, project, pki, secret_dir, artifacts, issuer):
    pki = Path(pki)
    original_backend = {p.name: p.read_bytes() for p in (pki / 'backend').iterdir()}
    original_kong = {p.name: p.read_bytes() for p in (pki / 'kong').iterdir()}
    evidence = []

    def output(args):
        try:
            return run(args, capture_output=True, text=True).stdout.strip()
        except subprocess.CalledProcessError as exc:
            raise AssertionError(exc.stderr.strip() or exc.stdout.strip() or 'Probe command failed') from None

    def probe(code):
        return output(compose + ['run', '--rm', '--no-deps', '-T', 'tests', 'python', '-c', code])

    def gateway_status():
        return int(probe("""from transport import http_client
with http_client('https://kong:8443') as c:
 status=c.get('/health').status_code
 if status==200:
  assert c.get('/health/ready').status_code==200
  assert c.get('/api/v1/products/').status_code==200
  assert c.get('/api/v1/auth/me').status_code==401
 print(status)
"""))

    def restart(service):
        output(compose + ['restart', service])
        # `kong health` only observes the nginx PID: it can succeed before the
        # proxy listener/configuration is usable. Probe the verified edge HTTPS
        # listener, including during deliberately broken upstream TLS cases.
        deadline = time.monotonic() + 45
        last_error = 'no probe completed'
        while time.monotonic() < deadline:
            try:
                if service == 'kong':
                    probe("""import ssl,socket,http.client
from pathlib import Path
c=ssl.create_default_context(cafile='/test-tls/trust/edge-ca.pem')
next_ca=Path('/test-tls/trust/edge-next.pem')
if next_ca.exists(): c.load_verify_locations(cafile=str(next_ca))
c.hostname_checks_common_name=False
with socket.create_connection(('kong',8443),2) as s:
 with c.wrap_socket(s,server_hostname='kong') as t:
  t.settimeout(3)
  t.sendall(b'GET /health HTTP/1.0\\r\\nHost: kong\\r\\n\\r\\n')
  response=http.client.HTTPResponse(t);response.begin()
  assert response.status in (200,502), 'Gateway not ready: '+str(response.status)
""")
                    return
                # Negative backend server certificates intentionally cannot
                # pass a certificate-validating application readiness check.
                output(compose + ['exec', '-T', service, 'python', '-c',
                                  "import socket; socket.create_connection(('localhost',8443),2).close()"])
                return
            except Exception as exc:
                last_error = str(exc)
            time.sleep(.5)
        raise AssertionError(service + ' TLS listener did not recover within 45s: ' + last_error)

    def restore():
        for directory, values in [('backend', original_backend), ('kong', original_kong)]:
            for filename, content in values.items():
                (pki / directory / filename).write_bytes(content)
        restart('backend')
        restart('kong')

    class TLSChecks(unittest.TestCase):
        def test_enrollment_configuration_fails_closed_for_ca_wrong_san_and_issuer(self):
            ca = (issuer.serialization.load_pem_private_key((pki / 'offline/client.key').read_bytes(), password=None),
                  issuer.x509.load_pem_x509_certificate((pki / 'offline/client.pem').read_bytes()))
            issuer.save_leaf(pki / 'negative', ca, 'wrong-client-san', ['other-client.internal'], client=True)
            cases = [(pki / 'trust/client-ca.pem', 'must be leaf certificates'),
                     (pki / 'negative/wrong-client-san.pem', 'Unexpected enrolled client identity'),
                     (pki / 'negative/untrusted.pem', 'not issued by a trusted client issuer')]
            for leaf, message in cases:
                with self.subTest(leaf=leaf.name):
                    try:
                        (pki / 'backend/client-pins.pem').write_bytes(original_backend['client-pins.pem'] + leaf.read_bytes())
                        output(compose + ['restart', 'backend'])
                        for _ in range(20):
                            info = json.loads(output(['docker', 'inspect', output(compose + ['ps', '-a', '-q', 'backend'])]))[0]
                            if info['State']['Status'] == 'exited':
                                break
                            time.sleep(0.5)
                        self.assertEqual(info['State']['Status'], 'exited')
                        self.assertNotEqual(info['State']['ExitCode'], 0)
                        self.assertIn(message, output(compose + ['logs', '--no-color', '--tail', '20', 'backend']))
                        evidence.append('Invalid enrollment ' + leaf.name + ': startup refused before listener; ' + message)
                    finally:
                        (pki / 'backend/client-pins.pem').write_bytes(original_backend['client-pins.pem'])
                        restart('backend')
                    self.assertEqual(gateway_status(), 200)

        def test_leaf_renewal_reuses_issuers_and_refuses_overwrite(self):
            renewed = issuer.generate(pki.parent / 'certs-renewed', ca_directory=pki / 'offline')
            for name in ('server', 'client', 'edge'):
                self.assertEqual((renewed / 'trust' / (name + '-ca.pem')).read_bytes(), (pki / 'trust' / (name + '-ca.pem')).read_bytes())
            self.assertNotEqual((renewed / 'kong/client.key').read_bytes(), original_kong['client.key'])
            with self.assertRaises(ValueError):
                issuer.generate(renewed)
            evidence.append('Leaf renewal: existing issuer trust preserved, new leaf keys generated; existing output directory refused')

        def test_external_published_https_with_verified_local_trust(self):
            binding = json.loads(output(['docker', 'inspect', output(compose + ['ps', '-q', 'kong'])]))[0]
            ports = binding['HostConfig']['PortBindings']
            self.assertEqual(set(ports), {'8443/tcp'})
            self.assertEqual(ports['8443/tcp'][0]['HostIp'], '127.0.0.1')
            port = binding['NetworkSettings']['Ports']['8443/tcp'][0]['HostPort']
            context = ssl.create_default_context(cafile=str(pki / 'trust/edge-ca.pem'))
            context.hostname_checks_common_name = False
            with urllib.request.urlopen('https://localhost:' + port + '/health', context=context, timeout=10) as response:
                self.assertEqual(response.status, 200)
            evidence.append('Published host HTTPS: trusted edge CA + localhost SAN -> HTTP 200')

        def test_runtime_mounts_exclude_offline_issuers_and_peer_private_keys(self):
            self.assertEqual(probe("from pathlib import Path; print(not Path('/test-tls/offline').exists())"), 'True')
            for service, directory in [('kong', 'kong'), ('backend', 'backend')]:
                info = json.loads(output(['docker', 'inspect', output(compose + ['ps', '-q', service])]))[0]
                tls = [m for m in info['Mounts'] if m['Destination'] == '/run/tls']
                self.assertEqual(len(tls), 1)
                self.assertFalse(tls[0]['RW'])
                source = tls[0]['Source'].replace('\\', '/')
                # Desktop may rebind a WSL source through an opaque mount ID.
                # Accept only that specific translation, and independently prove
                # the complete mounted file set/content on both native/Desktop.
                self.assertTrue(source.endswith('/certs/' + directory) or
                                re.fullmatch(r'/run/desktop/mnt/host/wsl/docker-desktop-bind-mounts/[^/]+/[a-f0-9]{64}', source))
                expected = {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                            for p in (pki / directory).iterdir() if p.is_file()}
                names = output(compose + ['exec', '-T', service, 'ls', '-A', '/run/tls']).splitlines()
                self.assertEqual(set(names), set(expected))
                for name, digest in expected.items():
                    self.assertRegex(name, r'^[a-zA-Z0-9_.-]+$')
                    actual = output(compose + ['exec', '-T', service, 'sha256sum', '/run/tls/' + name]).split()[0]
                    self.assertEqual(actual, digest, 'Mounted TLS file differs: ' + name)
                self.assertFalse(info['HostConfig']['PortBindings'] if service == 'backend' else False)
                self.assertTrue(all('/offline' not in m['Source'] for m in info['Mounts']))
            self.assertFalse((pki / 'backend/client.key').exists())
            self.assertFalse((pki / 'kong/server.key').exists())

        def test_kong_requires_upstream_validation_in_generated_nginx(self):
            config = output(compose + ['exec', '-T', 'kong', 'cat', '/run/kong/nginx-kong.conf'])
            for directive in ('proxy_ssl_verify on;', 'proxy_ssl_trusted_certificate /run/tls/server-ca.pem;',
                              'proxy_ssl_name        $upstream_host;', 'proxy_ssl_server_name on;',
                              'proxy_ssl_certificate /run/tls/client.pem;'):
                self.assertIn(directive, config)
            self.assertNotRegex(config, r'listen\s+[^;]*:8000')

        def test_expired_enrolled_client_rejected_during_handshake(self):
            try:
                (pki / 'backend/client-pins.pem').write_bytes(original_backend['client-pins.pem'] + (pki / 'negative/expired.pem').read_bytes())
                restart('backend')
                code = """import ssl,socket
c=ssl.create_default_context(cafile='/test-tls/trust/server-ca.pem')
c.maximum_version=ssl.TLSVersion.TLSv1_2
c.load_cert_chain('/test-tls/negative/expired.pem','/test-tls/negative/expired.key')
try:
 with socket.create_connection(('backend',8443),5) as s:
  with c.wrap_socket(s,server_hostname='backend') as t:
   t.sendall(b'GET /health HTTP/1.0\\r\\n\\r\\n'); t.recv(1024)
except ssl.SSLError as e:
 print(e.reason or str(e))
else: raise AssertionError('Expired enrolled client reached HTTP')
"""
                result = probe(code)
                evidence.append('Expired explicitly enrolled client: ' + result + '; no HTTP status')
            finally:
                (pki / 'backend/client-pins.pem').write_bytes(original_backend['client-pins.pem'])
                restart('backend')
            self.assertEqual(gateway_status(), 200)

        def test_enrolled_server_only_client_eku_rejected_during_handshake(self):
            try:
                (pki / 'backend/client-pins.pem').write_bytes(original_backend['client-pins.pem'] + (pki / 'negative/wrong-client-eku.pem').read_bytes())
                restart('backend')
                result = probe("""import ssl,socket
c=ssl.create_default_context(cafile='/test-tls/trust/server-ca.pem')
c.maximum_version=ssl.TLSVersion.TLSv1_2
c.load_cert_chain('/test-tls/negative/wrong-client-eku.pem','/test-tls/negative/wrong-client-eku.key')
try:
 with socket.create_connection(('backend',8443),5) as s:
  with c.wrap_socket(s,server_hostname='backend') as t:
   t.sendall(b'GET /health HTTP/1.0\\r\\n\\r\\n'); t.recv(1024)
except ssl.SSLError as e:
 print(e.reason or str(e))
else: raise AssertionError('Server-only client reached HTTP')
""")
                evidence.append('Explicitly enrolled wrong client EKU: ' + result + '; no HTTP status')
            finally:
                (pki / 'backend/client-pins.pem').write_bytes(original_backend['client-pins.pem'])
                restart('backend')
            self.assertEqual(gateway_status(), 200)

        def test_ca_and_leaf_rotation_overlap_retirement_and_rollback(self):
            new = issuer.generate(pki.parent / 'certs-next')
            (pki / 'negative/retired.pem').write_bytes(original_kong['client.pem'])
            (pki / 'negative/retired.key').write_bytes(original_kong['client.key'])
            try:
                # Stage trust and client enrollment BEFORE swapping any leaf/key.
                for peer in ('backend', 'kong'):
                    path = pki / peer / 'server-ca.pem'
                    path.write_bytes(path.read_bytes() + (new / 'trust/server-ca.pem').read_bytes())
                path = pki / 'backend/client-issuers.pem'
                path.write_bytes(path.read_bytes() + (new / 'backend/client-issuers.pem').read_bytes())
                path = pki / 'backend/client-pins.pem'
                path.write_bytes(path.read_bytes() + (new / 'backend/client-pins.pem').read_bytes())
                restart('backend')
                restart('kong')
                self.assertEqual(gateway_status(), 200)
                # New Kong client, old backend server (mixed generation).
                for name in ('client.pem', 'client.key'):
                    shutil.copyfile(new / 'kong' / name, pki / 'kong' / name)
                restart('kong')
                self.assertEqual(gateway_status(), 200)
                # New backend server + health identity, still overlapping trust.
                for name in ('server.pem', 'server.key', 'health.pem', 'health.key'):
                    shutil.copyfile(new / 'backend' / name, pki / 'backend' / name)
                restart('backend')
                self.assertEqual(gateway_status(), 200)
                # Retire old client pins and issuer trust. Existing valid peers recover.
                for peer in ('backend', 'kong'):
                    shutil.copyfile(new / peer / 'server-ca.pem', pki / peer / 'server-ca.pem')
                shutil.copyfile(new / 'backend/client-pins.pem', pki / 'backend/client-pins.pem')
                shutil.copyfile(new / 'backend/client-issuers.pem', pki / 'backend/client-issuers.pem')
                restart('backend')
                restart('kong')
                self.assertEqual(gateway_status(), 200)
                # Old CA/leaf client cannot regain HTTP even with the new server CA.
                result = probe("""import ssl,socket
c=ssl.create_default_context(cafile='/test-tls/kong/server-ca.pem')
c.maximum_version=ssl.TLSVersion.TLSv1_2
c.load_cert_chain('/test-tls/negative/retired.pem','/test-tls/negative/retired.key')
try:
 with socket.create_connection(('backend',8443),5) as s:
  with c.wrap_socket(s,server_hostname='backend') as t:
   t.sendall(b'GET /health HTTP/1.0\\r\\n\\r\\n'); data=t.recv(1024)
except ssl.SSLError as e: print(e.reason or str(e))
else: raise AssertionError('Retired issuer client reached HTTP')
""")
                evidence.append('CA/client leaf rotation: old -> overlap -> mixed generations -> new -> retired old client ' + result)
                # Edge CA rotation is independent; explicit client trust is replaced too.
                for name in ('edge.pem', 'edge.key'):
                    shutil.copyfile(new / 'kong' / name, pki / 'kong' / name)
                shutil.copyfile(new / 'trust/edge-ca.pem', pki / 'trust/edge-next.pem')
                restart('kong')
                self.assertEqual(probe("import ssl,httpx\nc=ssl.create_default_context(cafile='/test-tls/trust/edge-next.pem')\nprint(httpx.get('https://kong:8443/health',verify=c).status_code)"), '200')
                self.assertEqual(probe("""import ssl,httpx
c=ssl.create_default_context(cafile='/test-tls/trust/edge-ca.pem')
try: httpx.get('https://kong:8443/health',verify=c)
except httpx.ConnectError as e:
 assert 'CERTIFICATE_VERIFY_FAILED' in str(e)
 print('old edge trust rejected')
else: raise AssertionError('Old edge trust accepted new issuer')
"""), 'old edge trust rejected')
                evidence.append('Edge CA rotated independently: new edge trust -> 200; retired edge trust -> certificate verification failure')
            finally:
                restore()
            self.assertEqual(gateway_status(), 200)
            evidence.append('Rollback: matching original server/client/edge leaves and trust restored -> HTTP 200')

        def test_vite_proxy_uses_verified_https_and_rejects_wrong_ca(self):
            root = Path(__file__).resolve().parents[2]
            entry = root / 'frontend/node_modules/vite/bin/vite.js'
            self.assertTrue(entry.exists(), 'Run npm ci in frontend before the complete P2 runner')
            binding = json.loads(output(['docker', 'inspect', output(compose + ['ps', '-q', 'kong'])]))[0]
            gateway_port = binding['NetworkSettings']['Ports']['8443/tcp'][0]['HostPort']
            for ca, expected in [('edge-ca.pem', 200), ('server-ca.pem', 500)]:
                with socket.socket() as listener:
                    listener.bind(('127.0.0.1', 0))
                    port = listener.getsockname()[1]
                env = os.environ.copy()
                env.update(NODE_EXTRA_CA_CERTS=str(pki / 'trust' / ca), NODE_TLS_REJECT_UNAUTHORIZED='1',
                           API_PROXY_TARGET='https://localhost:' + gateway_port, VITE_API_BASE_URL='')
                env.pop('SSLKEYLOGFILE', None)
                with open(artifacts / ('vite-' + ca + '.txt'), 'w', encoding='utf-8') as log:
                    proc = subprocess.Popen(['node', str(entry), '--host', '127.0.0.1', '--port', str(port), '--strictPort'],
                                            cwd=root / 'frontend', env=env, stdout=log, stderr=subprocess.STDOUT,
                                            creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
                    try:
                        deadline = time.monotonic() + 45
                        while time.monotonic() < deadline:
                            try:
                                with urllib.request.urlopen('http://127.0.0.1:' + str(port) + '/health', timeout=3) as response:
                                    actual = response.status
                                break
                            except urllib.error.HTTPError as exc:
                                actual = exc.code
                                break
                            except (urllib.error.URLError, TimeoutError):
                                self.assertIsNone(proc.poll(), 'Vite exited before it was ready')
                                time.sleep(0.5)
                        else:
                            raise AssertionError('Vite did not start')
                        self.assertEqual(actual, expected)
                    finally:
                        proc.terminate()
                        proc.wait(timeout=10)
            evidence.append('Actual Vite proxy: correct Node extra CA -> 200; wrong CA -> TLS failure / proxy 500; secure=true')

        def test_runtime_logs_do_not_contain_keys_credentials_or_complete_jwt(self):
            logs = output(compose + ['logs', '--no-color'])
            for path in list(secret_dir.iterdir()) + list(pki.rglob('*.key')):
                self.assertNotIn(path.read_text().strip(), logs)
            self.assertNotRegex(logs, r'eyJ[A-Za-z0-9_-]{12,}\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+')
            self.assertNotIn('-----BEGIN PRIVATE KEY-----', logs)

    def invalid_server(fixture, error):
        def test(self):
            try:
                for suffix in ('.pem', '.key'):
                    shutil.copyfile(pki / 'negative' / (fixture + suffix), pki / 'backend' / ('server' + suffix))
                restart('backend')
                self.assertEqual(gateway_status(), 502)
                logs = output(compose + ['logs', '--no-color', '--tail', '30', 'kong'])
                self.assertIn(error, logs.lower())
                evidence.append('Kong rejects ' + fixture + ': upstream TLS error ' + error + ' -> HTTP 502 (gateway, not app 401/403)')
            finally:
                for name in ('server.pem', 'server.key'):
                    (pki / 'backend' / name).write_bytes(original_backend[name])
                restart('backend')
            self.assertEqual(gateway_status(), 200)
        return test

    def invalid_kong_client(fixture):
        def test(self):
            try:
                for suffix in ('.pem', '.key'):
                    shutil.copyfile(pki / 'negative' / (fixture + suffix), pki / 'kong' / ('client' + suffix))
                restart('kong')
                self.assertEqual(gateway_status(), 502)
                evidence.append('Actual Kong with ' + fixture + ' client: backend TLS rejects; Kong 502; no app 401/403')
            finally:
                for name in ('client.pem', 'client.key'):
                    (pki / 'kong' / name).write_bytes(original_kong[name])
                restart('kong')
            self.assertEqual(gateway_status(), 200)
        return test

    for fixture, error in [('wrong-san', 'does not match'), ('wrong-chain', 'unable to verify the first certificate'),
                           ('expired-server', 'certificate has expired'), ('wrong-server-eku', 'unsuitable certificate purpose')]:
        setattr(TLSChecks, 'test_kong_rejects_' + fixture.replace('-', '_'), invalid_server(fixture, error))
    for fixture in ('untrusted', 'expired'):
        setattr(TLSChecks, 'test_actual_kong_bad_client_' + fixture, invalid_kong_client(fixture))
    buffer = io.StringIO()
    result = unittest.TextTestRunner(stream=buffer, verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(TLSChecks))
    print(buffer.getvalue(), flush=True)
    print('\n'.join(evidence), flush=True)
    (artifacts / 'tls-host-checks.txt').write_text(buffer.getvalue(), encoding='utf-8')
    (artifacts / 'tls-evidence.txt').write_text('\n'.join(evidence), encoding='utf-8')
    (artifacts / 'tls-host-results.json').write_text(json.dumps({'tests': result.testsRun,
                                                              'failures': len(result.failures), 'errors': len(result.errors)}, indent=2))
    return result.wasSuccessful()
