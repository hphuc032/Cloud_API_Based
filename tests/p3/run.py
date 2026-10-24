"""Validate P3 plus complete P0/P1/P2 against isolated Compose data and PKI."""
from datetime import datetime, timezone
import argparse
import importlib.util
import json
import hashlib
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import uuid

ROOT = Path(__file__).resolve().parents[2]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--identity-only", action="store_true", help="Run P3 checks only; does not replace full regression")
    identity_only = parser.parse_args().identity_only
    artifacts = ROOT / "tests/p3/artifacts"
    if identity_only:
        artifacts = artifacts / "identity-only"
    artifacts.mkdir(parents=True, exist_ok=True)
    # Cloud checkout umasks can make public configs unreadable to nonroot images.
    # No secret, private key, application source, or executable mode is changed.
    for relative in ('gateway/kong.yml', 'monitoring/loki/loki-config.yml',
                     'monitoring/promtail/promtail-config.yml',
                     'docker/keycloak-entrypoint.sh', 'docker/keycloak/florasecure-realm.json',
                     'docker/keycloak/HealthProbe.java', 'docker/keycloak/nginx.conf'):
        (ROOT / relative).chmod(0o644)
    provisioning = ROOT / 'monitoring/grafana/provisioning'
    provisioning.chmod(0o755)
    for path in provisioning.rglob('*'):
        path.chmod(0o755 if path.is_dir() else 0o644)
    project = "cloud-api-p3-" + uuid.uuid4().hex[:12]
    env = {k: v for k, v in os.environ.items() if not k.startswith("COMPOSE_")}
    env["P3_RESULTS_DIR"] = str(artifacts)
    started = datetime.now(timezone.utc).isoformat()
    result, cleanup = 1, False
    commands = []
    with tempfile.TemporaryDirectory(prefix="cloud-api-p3-") as temp:
        secret_dir = Path(temp) / ".secrets"
        subprocess.run([sys.executable, str(ROOT / "docker/generate_secrets.py"),
                        "--new-deployment", "--directory", str(secret_dir)], check=True)
        # Exercise reserved URL characters without recording or displaying credentials.
        for name in ("migration_password", "runtime_password"):
            path = secret_dir / name
            path.write_text(path.read_text().strip() + "@:%/+\n")
        # Private temp parents keep these test-only mounts inaccessible on the host.
        # File-backed Compose secrets preserve source mode; Grafana reads as uid 472.
        for secret_file in secret_dir.iterdir():
            secret_file.chmod(0o444)
        env.update(SECRETS_DIR=str(secret_dir), APP_DB_NAME="p0_baseline", APP_ENV="test")
        pki_spec = importlib.util.spec_from_file_location('development_pki', ROOT / 'docker/pki.py')
        pki_module = importlib.util.module_from_spec(pki_spec)
        pki_spec.loader.exec_module(pki_module)
        pki_dir = pki_module.generate(Path(temp) / 'certs', test_fixtures=True)
        env['PKI_DIR'] = str(pki_dir)
        identity_spec = importlib.util.spec_from_file_location('identity_pki', ROOT / 'tests/p3/pki.py')
        identity_pki = importlib.util.module_from_spec(identity_spec)
        identity_spec.loader.exec_module(identity_pki)
        env['IDENTITY_TLS_DIR'] = str(identity_pki.generate(Path(temp) / 'identity-certs', pki_module))
        env['IDENTITY_HOSTNAME'] = 'https://identity-edge:8443'
        compose = ["docker", "compose", "--env-file", os.devnull, "-p", project,
                   "-f", str(ROOT / "docker/docker-compose.yml"),
                   "-f", str(ROOT / "tests/p1/compose.yml"),
                   "-f", str(ROOT / "tests/p2/compose.yml"),
                   "-f", str(ROOT / "tests/p3/compose.yml")]

        if env.get("P3_BUILD_OVERLAY"):
            compose += ["-f", env["P3_BUILD_OVERLAY"]]
        if env.get("P3_SOURCE_OVERLAY"):
            compose += ["-f",env["P3_SOURCE_OVERLAY"]]
        spec=importlib.util.spec_from_file_location('p3_probe_worker',ROOT/'tests/compose_probe.py')
        worker_module=importlib.util.module_from_spec(spec);spec.loader.exec_module(worker_module)
        worker=worker_module.ProbeWorker(compose)
        spec=importlib.util.spec_from_file_location('project_logs',ROOT/'tests/project_logs.py')
        log_module=importlib.util.module_from_spec(spec);spec.loader.exec_module(log_module)
        project_logs=log_module.ProjectLogs(project)
        if project_logs.desktop:
            log_root=Path(temp)/'project-logs';log_root.mkdir()
            env['DOCKER_LOG_ROOT']=str(log_root)

        def run(args, **kwargs):
            args=worker.command(args)
            commands.append(args)
            (artifacts/'commands.json').write_text(json.dumps(commands,indent=2))
            kwargs.setdefault('check', True)
            return subprocess.run(args, cwd=ROOT, env=env, **kwargs)

        try:
            if env.get('P3_TEST_BASE_IMAGE'):
                run(['docker','tag',env['P3_TEST_BASE_IMAGE'],project+'-tests'])
            reuse = env.get("P3_REUSE_PROJECT_IMAGES")
            if reuse:
                if not reuse.startswith('cloud-api-p3-') or not all(c.isalnum() or c=='-' for c in reuse):
                    raise ValueError('Only an explicit P3 test project image prefix may be reused')
                # Verify every container-executed Python source and the imported realm.
                # run.py drivers execute on the host, not in these images.
                sources = [ROOT/'backend/main.py']
                for directory in ('backend/app','backend/deployment','backend/alembic'):
                    sources.extend((ROOT/directory).rglob('*.py'))
                for phase in ('p0','p1','p2','p3'):
                    sources.extend(p for p in (ROOT/'tests'/phase).glob('*.py') if p.name!='run.py')
                paths = {str(p.relative_to(ROOT)):('/app/'+str(p.relative_to(ROOT/'backend')) if p.is_relative_to(ROOT/'backend') else '/'+str(p.relative_to(ROOT))) for p in sources}
                paths['docker/keycloak/florasecure-realm.json']='/realm.json'
                expected = {name:hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in paths}
                code = "import hashlib,json; from pathlib import Path; paths="+repr(paths)+"; print(json.dumps({name:hashlib.sha256(Path(path).read_bytes()).hexdigest() for name,path in paths.items()}))"
                actual = json.loads(run(['docker','run','--rm','--network','none','--entrypoint','python',reuse+'-tests','-c',code],capture_output=True,text=True).stdout)
                if actual != expected:
                    raise RuntimeError('Reused test image source differs from the checkout; rebuild required')
                roles = ['backend','db-bootstrap','migrate','identity-bootstrap']
                roots = json.loads(run(['docker','image','inspect',*[reuse+'-'+role for role in roles]],capture_output=True,text=True).stdout)
                if any(image['RootFS']['Layers']!=roots[0]['RootFS']['Layers'] for image in roots):
                    raise RuntimeError('Reused application job images have different filesystems')
                for service in roles+['tests']:
                    run(['docker','image','tag',reuse+'-'+service,project+'-'+service])
            else:
                run(compose + ["build"])
            # Opt-in for small isolated cloud hosts using Docker's copy-heavy vfs driver.
            # Final images are retained; only unused builder cache is released.
            if env.get("P3_RELEASE_BUILD_CACHE") == "1":
                run(["docker", "builder", "prune", "--all", "--force"])

            historical = []
            if env.get('P3_RELEASE_EXITED_JOBS') == '1':
                # Optional disk-bounded orchestration for copy-heavy vfs hosts.
                # Keep migrate for the existing restart/no-rerun assertion.
                def up(*services):
                    run(compose+['up','--no-deps','-d','--wait','--wait-timeout','300',*services])
                up('postgres','identity-db')
                for service in ('db-bootstrap','identity-bootstrap','migrate'):
                    run(compose+['up','--no-deps','-d',service])
                    job_ids=run(compose+['ps','-a','-q',service],capture_output=True,text=True).stdout.split()
                    assert len(job_ids)==1
                    assert run(['docker','wait',job_ids[0]],capture_output=True,text=True).stdout.strip()=='0'
                    if service!='migrate':
                        ids=run(compose+['ps','-a','-q',service],capture_output=True,text=True).stdout.split()
                        records=json.loads(run(['docker','inspect',*ids],capture_output=True,text=True).stdout)
                        assert len(records)==1 and records[0]['State']['Status']=='exited' and records[0]['State']['ExitCode']==0
                        historical.extend(records)
                        run(compose+['rm','--force',service])
                up('backend','keycloak');up('identity-edge','kong','loki');up('grafana','promtail')
            else:
                run(compose + ["up", "-d", "--wait", "--wait-timeout", "300",
                               "backend", "kong", "keycloak", "identity-edge", "grafana", "promtail"])
            if project_logs.desktop:
                overlay=Path(temp)/'desktop-collector.json'
                overlay.write_text(json.dumps(project_logs.overlay(run,'promtail',log_root)))
                compose+=['-f',str(overlay)]
                run(compose+['up','--no-deps','-d','--force-recreate','promtail'])
            ids = run(compose + ["ps", "-a", "-q"], capture_output=True, text=True).stdout.split()
            metadata = json.loads(run(["docker", "inspect", *ids], capture_output=True, text=True).stdout)+historical
            (artifacts / "containers.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
            if env.get('P3_SOURCE_OVERLAY'):
                sources=[]
                for directory in ('backend/app','backend/deployment','backend/alembic','tests'):
                    sources.extend(p for p in (ROOT/directory).rglob('*.py') if 'artifacts' not in p.relative_to(ROOT).parts and '__pycache__' not in p.parts)
                sources.append(ROOT/'backend/main.py')
                paths={str(p.relative_to(ROOT)):('/app/'+str(p.relative_to(ROOT/'backend')) if p.is_relative_to(ROOT/'backend') else '/'+str(p.relative_to(ROOT))) for p in sources}
                paths['docker/keycloak/florasecure-realm.json']='/realm.json'
                expected={name:hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in paths}
                code='import hashlib,json;from pathlib import Path;paths='+repr(paths)+';print(json.dumps({n:hashlib.sha256(Path(p).read_bytes()).hexdigest() for n,p in paths.items()}))'
                actual=json.loads(run(compose+['run','--rm','--no-deps','-T','tests','python','-c',code],capture_output=True,text=True).stdout)
                if actual!=expected:raise RuntimeError('Mounted test sources differ from checkout')
                (artifacts/'image-source-evidence.json').write_text(json.dumps({'verified':True,'sha256':actual},indent=2))
            result = 0  # Startup succeeded; retain every later nonzero result.
            proc = run(compose + ['run', '--rm', '--no-deps', '-T', 'tests',
                                  'python', '/tests/p3/launch.py'], check=False,
                       stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
            print(proc.stdout, flush=True)
            (artifacts / 'p3-pytest.txt').write_text(proc.stdout, encoding='utf-8')
            if proc.returncode:
                result = 1
            spec = importlib.util.spec_from_file_location('identity_checks', ROOT / 'tests/p3/host_checks.py')
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            if not module.execute(run, compose, project, metadata, artifacts):
                result = 1
            if not identity_only:
                proc = run(compose + ["run", "--rm", "--no-deps", "-T", "tests"],
                           check=False, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
                print(proc.stdout, flush=True)
                (artifacts / "pytest.txt").write_text(proc.stdout, encoding="utf-8")
                if proc.returncode:
                    result = 1
                host_file = ROOT / "tests/p1/host_checks.py"
                if host_file.exists():
                    spec = importlib.util.spec_from_file_location("host_checks", host_file)
                    module = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(module)
                    private_keys = [p.read_bytes().strip() for directory in (pki_dir, Path(env['IDENTITY_TLS_DIR'])) for p in directory.rglob('*.key')]
                    if not module.execute(run, compose, project, metadata, secret_dir, artifacts, private_keys):
                        result = 1
                proc = run(compose + ['run', '--rm', '--no-deps', '-T', 'tests',
                                                'python', '/tests/p2/launch.py'],
                           check=False, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
                print(proc.stdout, flush=True)
                (artifacts / 'p2-pytest.txt').write_text(proc.stdout, encoding='utf-8')
                if proc.returncode:
                    result = 1
                if env.get('P3_PROBE_BASE_IMAGE'):
                    run(['docker','tag',env['P3_PROBE_BASE_IMAGE'],project+'-tests'])
                if env.get('CLOUD_API_KEEP_PROBES')=='1':worker.start(run,project)
                spec = importlib.util.spec_from_file_location('tls_checks', ROOT / 'tests/p2/host_checks.py')
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                if not module.execute(run, compose, project, pki_dir, secret_dir, artifacts, pki_module):
                    result = 1
        except subprocess.CalledProcessError as exc:
            result = 1
            print(f"P3 command failed (exit {exc.returncode}); no acceptance claimed.", flush=True)
            # Deployment scripts never print credentials. Keep full local diagnostics ignored.
            logs = subprocess.run(compose + ["logs", "--no-color", "--tail", "80"],
                                  cwd=ROOT, env=env, capture_output=True, text=True)
            (artifacts / "deployment-failure.txt").write_text(logs.stdout + logs.stderr, encoding="utf-8")
        finally:
            worker.close(run)
            try:
                run(compose + ["down", "--volumes", "--remove-orphans", "--timeout", "10"])
                cleanup = True
            except subprocess.CalledProcessError:
                print(f"Cleanup failed: remove ONLY project {project}", file=sys.stderr)
            project_logs.close(run)
            (artifacts / "run.json").write_text(json.dumps({
                "project": project, "exit_code": result, "cleanup_completed": cleanup,
                "started_utc": started, "identity_only": identity_only, "finished_utc": datetime.now(timezone.utc).isoformat(),
            }, indent=2), encoding="utf-8")
            (artifacts / 'commands.json').write_text(json.dumps(commands, indent=2), encoding='utf-8')
    return result if cleanup else 1


if __name__ == "__main__":
    sys.exit(main())
