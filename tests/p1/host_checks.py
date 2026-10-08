"""Host-side evidence against actual container namespaces, images and failure modes."""
import gzip
import io
import json
import subprocess
import tarfile
import tempfile
import time
import unittest


def execute(run, compose, project, metadata, secret_dir, artifacts, extra_secret_values=()):
    containers = {c["Config"]["Labels"]["com.docker.compose.service"]: c for c in metadata}
    probe_image = project + "-tests"

    def output(args):
        return run(args, capture_output=True, text=True).stdout.strip()

    def probe(service, code):
        return output(["docker", "run", "--rm", "--network", "container:" + containers[service]["Id"],
                       "--entrypoint", "python", probe_image, "-c", code])

    def http_status(path):
        return output(compose + ["exec", "-T", "backend", "python", "-c",
            "import urllib.error\nfrom deployment.health import status\ntry:\n print(status('" + path +
            "'))\nexcept urllib.error.HTTPError as e:\n print(e.code)"])

    db_ip = containers["postgres"]["NetworkSettings"]["Networks"][project + "_app_data"]["IPAddress"]

    class DeploymentChecks(unittest.TestCase):
        def test_exact_network_memberships(self):
            expected = {
                "postgres": {"app_data"}, "db-bootstrap": {"app_data"}, "migrate": {"app_data"},
                "backend": {"api_transport", "app_data"}, "kong": {"edge", "api_transport"},
                "keycloak": {"identity_transport", "identity_data"}, "identity-db": {"identity_data"}, "identity-bootstrap": {"identity_data"}, "identity-edge": {"identity_transport"}, "loki": {"observability"},
                "promtail": {"observability"}, "grafana": {"observability"},
            }
            for service, networks in expected.items():
                with self.subTest(service=service):
                    actual = set(containers[service]["NetworkSettings"]["Networks"])
                    self.assertEqual(actual, {project + "_" + n for n in networks})
            for name in ("app_data", "identity_data", "observability"):
                network = json.loads(output(["docker", "network", "inspect", project + "_" + name]))[0]
                self.assertTrue(network["Internal"])
            api_network = json.loads(output(["docker", "network", "inspect", project + "_api_transport"]))[0]
            self.assertFalse(api_network["Internal"])

        def test_postgres_no_published_port(self):
            self.assertFalse(containers["postgres"]["HostConfig"]["PortBindings"])
            self.assertTrue(all(v is None for v in containers["postgres"]["NetworkSettings"]["Ports"].values()))
            self.assertNotEqual(containers["postgres"]["HostConfig"]["NetworkMode"], "host")
            # Test overlay does not remove any postgres port: inspect the actual base file as well.
            config = json.loads(output(compose[:compose.index("-f", compose.index("-f") + 1)] + ["config", "--format", "json"]))
            self.assertFalse(config["services"]["postgres"].get("ports"))

        def test_migration_jobs_completed_before_backend(self):
            for service in ("db-bootstrap", "migrate"):
                self.assertEqual(containers[service]["State"]["ExitCode"], 0)
                self.assertEqual(containers[service]["State"]["Status"], "exited")
            self.assertLess(containers["migrate"]["State"]["FinishedAt"], containers["backend"]["State"]["StartedAt"])
            self.assertEqual(containers["backend"]["Config"]["Cmd"], ["python", "-m", "deployment.serve"])

        def test_secret_mounts_and_docker_api_absence(self):
            expected = {
                "backend": {"runtime_password", "jwt_secret", "webhook_secret"},
                "migrate": {"migration_password"},
                "db-bootstrap": {"postgres_password", "migration_password", "runtime_password"},
                "postgres": {"postgres_password"}, "keycloak": {"keycloak_admin_password", "identity_db_password"}, "identity-db": {"identity_admin_password"}, "identity-bootstrap": {"identity_admin_password", "identity_db_password"}, "identity-edge": set(),
                "grafana": {"grafana_admin_password"}, "kong": set(), "loki": set(), "promtail": set(),
            }
            values = [p.read_text().strip() for p in secret_dir.iterdir()]
            for service, container in containers.items():
                mounts = container["Mounts"]
                actual = {m["Destination"].split("/")[-1] for m in mounts if m["Destination"].startswith("/run/secrets/")}
                self.assertEqual(actual, expected[service])
                self.assertFalse(any("docker.sock" in m["Destination"] for m in mounts))
                self.assertFalse(container["HostConfig"]["Privileged"])
                for value in values:
                    self.assertNotIn(value, json.dumps(container["Config"]))

        def test_no_runtime_secrets_in_built_image_layers(self):
            needles = [p.read_bytes().strip() for p in secret_dir.iterdir()]
            needles.extend(extra_secret_values)
            images = [containers[s]["Image"] for s in ("backend", "db-bootstrap", "migrate")]
            images.append(probe_image)
            with tempfile.TemporaryDirectory(prefix="p1-image-audit-") as tmp:
                archive = tmp + "/images.tar"
                run(["docker", "image", "save", "-o", archive, *images], capture_output=True)
                with tarfile.open(archive) as tar:
                    for member in tar:
                        if not member.isfile():
                            continue
                        stream = tar.extractfile(member)
                        prefix = stream.read(2)
                        stream.seek(0)
                        if prefix == b"\x1f\x8b":
                            stream = gzip.GzipFile(fileobj=stream)
                        tail = b""
                        while True:
                            block = stream.read(1024 * 1024)
                            if not block:
                                break
                            chunk = tail + block
                            self.assertFalse(any(value in chunk for value in needles), "Runtime secret found in image layer")
                            tail = chunk[-max(512, max(map(len, needles))):]
            self.assertEqual(probe("backend", "from pathlib import Path; print(not Path('/app/.env').exists() and not Path('/app/.secrets').exists())"), "True")

        def test_readiness_migration_mismatch(self):
            self.assertEqual(http_status("/health/ready"), "200")
            command = compose + ["exec", "-T", "postgres", "psql", "-U", "postgres", "-d", "p0_baseline", "-c"]
            try:
                output(command + ["UPDATE alembic_version SET version_num='p1_probe'"])
                self.assertEqual(http_status("/health/ready"), "503")
                self.assertEqual(http_status("/health"), "200")
            finally:
                output(command + ["UPDATE alembic_version SET version_num='0002_external_identities'"])
            self.assertEqual(http_status("/health/ready"), "200")

        def test_readiness_database_outage_and_recovery(self):
            try:
                output(compose + ["stop", "postgres"])
                for _ in range(3):
                    started = time.monotonic()
                    self.assertEqual(http_status("/health/ready"), "503")
                    self.assertLess(time.monotonic() - started, 5)
                self.assertEqual(http_status("/health"), "200")
            finally:
                output(compose + ["start", "postgres"])
            deadline = time.monotonic() + 45
            while time.monotonic() < deadline:
                if http_status("/health/ready") == "200":
                    break
                time.sleep(1)
            self.assertEqual(http_status("/health/ready"), "200")

        def test_backend_restart_does_not_run_migrations(self):
            before = output(compose + ["ps", "-a", "-q", "migrate"])
            output(compose + ["restart", "backend"])
            for _ in range(30):
                try:
                    if http_status("/health/ready") == "200":
                        break
                except subprocess.CalledProcessError:
                    pass
                time.sleep(1)
            self.assertEqual(http_status("/health/ready"), "200")
            self.assertEqual(output(compose + ["ps", "-a", "-q", "migrate"]), before)
            state = json.loads(output(["docker", "inspect", before]))[0]
            self.assertEqual(state["State"]["FinishedAt"], containers["migrate"]["State"]["FinishedAt"])

        def test_public_dns_for_current_ssrf_validation(self):
            self.assertEqual(probe("backend", "import socket; print(bool(socket.getaddrinfo('example.com',443)))"), "True")

        def test_observability_readiness_and_backend_ingestion(self):
            code = """import json,time,urllib.request,urllib.parse
assert urllib.request.urlopen('http://promtail:9080/ready',timeout=5).status==200
assert urllib.request.urlopen('http://grafana:3000/api/health',timeout=5).status==200
query=urllib.parse.urlencode({'query':'{service="backend"}', 'limit':'1'})
for _ in range(30):
 data=json.load(urllib.request.urlopen('http://loki:3100/loki/api/v1/query_range?'+query,timeout=5))
 if data['data']['result']:
  print('True'); break
 time.sleep(1)
else: raise AssertionError('No backend logs in Loki')
"""
            self.assertEqual(probe("loki", code), "True")

    def connectivity(service, allowed):
        def test(self):
            code = ("import socket\nfor host in ['postgres', '" + db_ip + "']:\n"
                    " try:\n  s=socket.create_connection((host,5432),2); s.close(); print('reachable')\n"
                    " except OSError:\n  print('blocked')")
            self.assertEqual(probe(service, code).splitlines(), ["reachable" if allowed else "blocked"] * 2)
        return test

    for service in ("backend", "kong", "keycloak", "loki", "promtail", "grafana"):
        setattr(DeploymentChecks, "test_db_reachability_" + service, connectivity(service, service == "backend"))
    buffer = io.StringIO()
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(DeploymentChecks)
    result = unittest.TextTestRunner(stream=buffer, verbosity=2).run(suite)
    print(buffer.getvalue(), flush=True)
    (artifacts / "host-checks.txt").write_text(buffer.getvalue(), encoding="utf-8")
    (artifacts / "host-results.json").write_text(json.dumps({
        "tests": result.testsRun, "failures": len(result.failures), "errors": len(result.errors),
    }, indent=2), encoding="utf-8")
    return result.wasSuccessful()
