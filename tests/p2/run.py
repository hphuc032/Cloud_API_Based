"""Validate P2 plus complete P0/P1 against isolated Compose data and PKI."""
from datetime import datetime, timezone
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import uuid

ROOT = Path(__file__).resolve().parents[2]


def main():
    artifacts = ROOT / "tests/p2/artifacts"
    artifacts.mkdir(exist_ok=True)
    project = "cloud-api-p2-" + uuid.uuid4().hex[:12]
    env = {k: v for k, v in os.environ.items() if not k.startswith("COMPOSE_")}
    started = datetime.now(timezone.utc).isoformat()
    result, cleanup = 1, False
    commands = []
    with tempfile.TemporaryDirectory(prefix="cloud-api-p2-") as temp:
        secret_dir = Path(temp) / ".secrets"
        subprocess.run([sys.executable, str(ROOT / "docker/generate_secrets.py"),
                        "--new-deployment", "--directory", str(secret_dir)], check=True)
        # Exercise reserved URL characters without recording or displaying credentials.
        for name in ("migration_password", "runtime_password"):
            path = secret_dir / name
            path.write_text(path.read_text().strip() + "@:%/+\n")
        env.update(SECRETS_DIR=str(secret_dir), APP_DB_NAME="p0_baseline", APP_ENV="test")
        pki_spec = importlib.util.spec_from_file_location('development_pki', ROOT / 'docker/pki.py')
        pki_module = importlib.util.module_from_spec(pki_spec)
        pki_spec.loader.exec_module(pki_module)
        pki_dir = pki_module.generate(Path(temp) / 'certs', test_fixtures=True)
        env['PKI_DIR'] = str(pki_dir)
        compose = ["docker", "compose", "--env-file", os.devnull, "-p", project,
                   "-f", str(ROOT / "docker/docker-compose.yml"),
                   "-f", str(ROOT / "tests/p1/compose.yml"),
                   "-f", str(ROOT / "tests/p2/compose.yml")]

        def run(args, **kwargs):
            commands.append(args)
            kwargs.setdefault('check', True)
            return subprocess.run(args, cwd=ROOT, env=env, **kwargs)

        try:
            run(compose + ["build"])
            run(compose + ["up", "-d", "--wait", "--wait-timeout", "300",
                           "backend", "kong", "keycloak", "grafana", "promtail"])
            ids = run(compose + ["ps", "-a", "-q"], capture_output=True, text=True).stdout.split()
            metadata = json.loads(run(["docker", "inspect", *ids], capture_output=True, text=True).stdout)
            (artifacts / "containers.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
            proc = run(compose + ["run", "--rm", "--no-deps", "-T", "tests"],
                       check=False, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
            print(proc.stdout, flush=True)
            (artifacts / "pytest.txt").write_text(proc.stdout, encoding="utf-8")
            result = proc.returncode
            host_file = ROOT / "tests/p1/host_checks.py"
            if host_file.exists():
                spec = importlib.util.spec_from_file_location("host_checks", host_file)
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                private_keys = [p.read_bytes().strip() for p in pki_dir.rglob('*.key')]
                if not module.execute(run, compose, project, metadata, secret_dir, artifacts, private_keys):
                    result = 1
            proc = run(compose + ['run', '--rm', '--no-deps', '-T', 'tests',
                                            'python', '/tests/p2/launch.py'],
                       check=False, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
            print(proc.stdout, flush=True)
            (artifacts / 'p2-pytest.txt').write_text(proc.stdout, encoding='utf-8')
            if proc.returncode:
                result = 1
            spec = importlib.util.spec_from_file_location('tls_checks', ROOT / 'tests/p2/host_checks.py')
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            if not module.execute(run, compose, project, pki_dir, secret_dir, artifacts, pki_module):
                result = 1
        except subprocess.CalledProcessError as exc:
            print(f"P2 command failed (exit {exc.returncode}); no acceptance claimed.", flush=True)
            # Deployment scripts never print credentials. Keep full local diagnostics ignored.
            logs = subprocess.run(compose + ["logs", "--no-color", "--tail", "80"],
                                  cwd=ROOT, env=env, capture_output=True, text=True)
            (artifacts / "deployment-failure.txt").write_text(logs.stdout + logs.stderr, encoding="utf-8")
        finally:
            try:
                run(compose + ["down", "--volumes", "--remove-orphans", "--timeout", "10"])
                cleanup = True
            except subprocess.CalledProcessError:
                print(f"Cleanup failed: remove ONLY project {project}", file=sys.stderr)
            (artifacts / "run.json").write_text(json.dumps({
                "project": project, "exit_code": result, "cleanup_completed": cleanup,
                "started_utc": started, "finished_utc": datetime.now(timezone.utc).isoformat(),
            }, indent=2), encoding="utf-8")
            (artifacts / 'commands.json').write_text(json.dumps(commands, indent=2), encoding='utf-8')
    return result if cleanup else 1


if __name__ == "__main__":
    sys.exit(main())
