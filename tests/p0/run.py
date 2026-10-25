"""Run only disposable P0 infrastructure; Python 3.9+ and Docker Compose required."""
import json
import os
from pathlib import Path
import secrets
import subprocess
import sys
import uuid
from datetime import datetime, timezone


def main():
    root = Path(__file__).resolve().parents[2]
    artifacts = root / "tests/p0/artifacts"
    artifacts.mkdir(exist_ok=True)
    project = "cloud-api-p0-" + uuid.uuid4().hex[:12]
    started = datetime.now(timezone.utc).isoformat()
    env = os.environ.copy()
    env.update({name: secrets.token_hex(32) for name in
                ("P0_DB_PASSWORD", "P0_JWT_SECRET", "P0_WEBHOOK_SECRET")})
    # Ignore ambient Compose overrides and user .env files.
    for name in list(env):
        if name.startswith("COMPOSE_"):
            del env[name]
    compose = ["docker", "compose", "--env-file", os.devnull, "-p", project,
               "-f", str(root / "tests/p0/compose.yml")]

    def run(args, **kwargs):
        return subprocess.run(args, cwd=root, env=env, check=True, **kwargs)

    result = 1
    cleanup = False
    try:
        run(compose + ["build"])
        run(compose + ["up", "-d", "--wait", "--wait-timeout", "180",
                       "postgres", "backend", "kong"])
        images = run(compose + ["images", "--format", "json"],
                     capture_output=True, text=True).stdout
        (artifacts / "images.json").write_text(images, encoding="utf-8")
        for service in ("backend", "tests"):
            args = (["exec", "-T", service] if service == "backend" else
                    ["run", "--rm", "--no-deps", "-T", service])
            # Runtime images need not ship their installation tool. Read installed
            # distribution metadata without requiring pip inside the application.
            inventory = ("from importlib.metadata import distributions; "
                         "print('\\n'.join(sorted(d.metadata['Name']+'=='+d.version "
                         "for d in distributions())))")
            packages = run(compose + args + ["python", "-c", inventory],
                           capture_output=True, text=True).stdout
            (artifacts / f"{service}-packages.txt").write_text(packages, encoding="utf-8")
        proc = subprocess.run(compose + ["run", "--rm", "-T", "tests"],
                              cwd=root, env=env, stdout=subprocess.PIPE,
                              stderr=subprocess.STDOUT, text=True)
        # No environment, token, or request-body logging; keep pytest locals disabled.
        print(proc.stdout, end="", flush=True)
        (artifacts / "pytest.txt").write_text(proc.stdout, encoding="utf-8")
        result = proc.returncode
    except subprocess.CalledProcessError as exc:
        print(f"P0 infrastructure command failed (exit {exc.returncode}).", file=sys.stderr)
    finally:
        try:
            run(compose + ["down", "--volumes", "--remove-orphans", "--timeout", "10"])
            cleanup = True
        except subprocess.CalledProcessError:
            print(f"Cleanup failed: remove ONLY Compose project {project}.", file=sys.stderr)
        (artifacts / "run.json").write_text(json.dumps({
            "project": project, "test_exit_code": result, "cleanup_completed": cleanup,
            "started_utc": started, "finished_utc": datetime.now(timezone.utc).isoformat(),
        }, indent=2) + "\n", encoding="utf-8")
    return result if cleanup else 1


if __name__ == "__main__":
    sys.exit(main())
