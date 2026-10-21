"""P5 hardening candidate on disposable Compose volumes and ephemeral reviewed identities.

No production data, cloud DNS substitution, or TLS verification exceptions.
"""
import importlib.util
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import uuid
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[2]


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--focus',choices=['browser','rotation','hardening'],
                        help='Fresh disposable focused recovery; never replaces the full suite')
    focus=parser.parse_args().focus
    artifacts = ROOT / 'tests/p5/artifacts'
    if focus:artifacts=artifacts/('focused-'+focus)
    artifacts.mkdir(parents=True, exist_ok=True)
    project = 'cloud-api-p5-' + uuid.uuid4().hex[:12]
    env = {k:v for k,v in os.environ.items() if not k.startswith('COMPOSE_')}
    if focus:
        env['P5_CORE_ONLY']='1'
        os.environ['P5_CORE_ONLY']='1'
    commands = []
    results = {}
    started = datetime.now(timezone.utc).isoformat()
    with tempfile.TemporaryDirectory(prefix=project+'-') as temp:
        temp = Path(temp)
        secret_dir = temp / '.secrets'
        subprocess.run([sys.executable,str(ROOT/'docker/generate_secrets.py'),
                        '--new-deployment','--directory',str(secret_dir)],check=True)
        for path in secret_dir.iterdir():path.chmod(0o444)
        pki_module = module('p4_pki',ROOT/'docker/pki.py')
        pki = pki_module.generate(temp/'certs',test_fixtures=True)
        identity_pki = module('p4_identity_pki',ROOT/'tests/p3/pki.py').generate(temp/'identity-certs',pki_module)
        fixtures = temp/'fixtures';fixtures.mkdir(mode=0o700)
        env.update(SECRETS_DIR=str(secret_dir),PKI_DIR=str(pki),IDENTITY_TLS_DIR=str(identity_pki),
                   APP_DB_NAME='p0_baseline',APP_ENV='test',IDENTITY_HOSTNAME='https://identity-edge:8443',
                   OIDC_ORIGINS=json.dumps(['https://localhost:5173','https://localhost:5174']),
                   P4_RESULTS_DIR=str(artifacts),P4_FIXTURES_DIR=str(fixtures))
        compose = ['docker','compose','--env-file',os.devnull,'-p',project]
        for relative in ('docker/docker-compose.yml','tests/p1/compose.yml','tests/p2/compose.yml',
                         'tests/p3/compose.yml','docker/p4-compose.yml','tests/p4/compose.yml','tests/p5/compose.yml'):
            compose += ['-f',str(ROOT/relative)]
        if env.get('P4_BUILD_OVERLAY'):compose += ['-f',env['P4_BUILD_OVERLAY']]
        if env.get('P5_SOURCE_OVERLAY'):compose += ['-f',env['P5_SOURCE_OVERLAY']]
        worker=module('p4_probe_worker',ROOT/'tests/compose_probe.py').ProbeWorker(compose)

        def run(args,**kwargs):
            args=worker.command(args)
            commands.append(args)
            kwargs.setdefault('check',True)
            kwargs.setdefault('cwd',ROOT);kwargs.setdefault('env',env)
            return subprocess.run(args,**kwargs)

        def capture(name,args):
            proc = run(args,check=False,capture_output=True,text=True)
            output = proc.stdout+proc.stderr
            (artifacts/(name+'.txt')).write_text(output)
            print(output,flush=True)
            results[name] = proc.returncode
            return proc.returncode==0

        try:
            if env.get('P5_TEST_BASE_IMAGE'):
                run(['docker','tag',env['P5_TEST_BASE_IMAGE'],project+'-tests'])
            run(compose+['build'])
            if env.get('P4_RELEASE_BUILD_CACHE')=='1':run(['docker','builder','prune','--all','--force'])
            historical=[]
            if env.get('P4_RELEASE_EXITED_JOBS')=='1':
                historical=module('p4_startup',ROOT/'tests/p5/startup.py').start(run,compose)
            else:
                run(compose+['up','-d','--wait','--wait-timeout','300',
                             'backend','kong','keycloak','identity-edge','grafana','promtail'])
            results['startup'] = 0
            ids = run(compose+['ps','-a','-q'],capture_output=True,text=True).stdout.split()
            metadata = json.loads(run(['docker','inspect',*ids],capture_output=True,text=True).stdout)+historical
            (artifacts/'containers.json').write_text(json.dumps(metadata,indent=2))
            sources=[]
            for directory in ('backend/app','backend/deployment','backend/alembic','tests'):
                sources.extend(p for p in (ROOT/directory).rglob('*.py') if 'artifacts' not in p.parts and '__pycache__' not in p.parts)
            sources.append(ROOT/'backend/main.py')
            paths={str(p.relative_to(ROOT)):('/app/'+str(p.relative_to(ROOT/'backend')) if p.is_relative_to(ROOT/'backend') else '/'+str(p.relative_to(ROOT))) for p in sources}
            paths.update({'docker/keycloak/florasecure-realm.json':'/realm.json',
                          'docker/keycloak/florasecure-p4-realm.json':'/realm-p4.json',
                          'docker/keycloak/florasecure-p5-realm.json':'/realm-p5.json'})
            expected={name:hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in paths}
            code='import hashlib,json;from pathlib import Path;paths='+repr(paths)+';print(json.dumps({name:hashlib.sha256(Path(path).read_bytes()).hexdigest() for name,path in paths.items()}))'
            actual=json.loads(run(compose+['run','--rm','--no-deps','-T','tests','python','-c',code],capture_output=True,text=True).stdout)
            if actual!=expected:raise RuntimeError('Built container sources differ from the checkout')
            (artifacts/'image-source-evidence.json').write_text(json.dumps({'verified':True,'sha256':actual},indent=2))
            run(compose+['run','--rm','--no-deps','-T','-e','PYTHONPATH=/app:/tests/p0:/tests/p3',
                         'tests','python','/tests/p4/bootstrap.py'])
            # Import a generated signing provider only in this disposable IdP.
            run(compose+['run','--rm','--no-deps','-T','kong-keys'])
            run(compose+['exec','-T','kong','kong','config','parse','/gateway/kong.json'],capture_output=True)
            run(compose+['exec','-T','kong','kong','reload'],capture_output=True)
            if focus=='hardening':
                capture('p5-hardening',compose+['run','--rm','--no-deps','-T','tests','python','/tests/p5/launch.py'])
            if not focus:
                capture('p5-hardening',compose+['run','--rm','--no-deps','-T','tests','python','/tests/p5/launch.py'])
                capture('p4-focused',compose+['run','--rm','--no-deps','-T','tests','python','/tests/p4/launch.py','--focused'])
                capture('p4-pytest',compose+['run','--rm','--no-deps','-T','tests','python','/tests/p4/launch.py'])
                if env.get('P5_PROBE_BASE_IMAGE'):
                    run(['docker','tag',env['P5_PROBE_BASE_IMAGE'],project+'-tests'])
                if env.get('CLOUD_API_KEEP_PROBES')=='1':worker.start(run,project)
                checks = module('p4_host_checks',ROOT/'tests/p4/host_checks.py')
                results['p4-host'] = 0 if checks.execute(run,compose,project,metadata,artifacts) else 1
                identity_checks = module('p4_identity_checks',ROOT/'tests/p3/host_checks.py')
                results['p3-host'] = 0 if identity_checks.execute(run,compose,project,metadata,artifacts) else 1
                tls = module('p4_tls_checks',ROOT/'tests/p2/host_checks.py')
                results['p2-host'] = 0 if tls.execute(run,compose,project,pki,secret_dir,artifacts,pki_module) else 1
                worker.close(run)
            if focus not in ('rotation','hardening'):
                results['p4-browser'] = 0 if module('p5_sdk_browser',ROOT/'tests/p4/browser_host.py').execute(
                    run,compose,project,metadata,pki,identity_pki,fixtures,temp,artifacts,env) else 1
            browser_file = ROOT/'tests/p5/browser_host.py'
            if focus in ('rotation','hardening'):pass
            elif browser_file.exists():
                results['browser'] = 0 if module('p4_browser',browser_file).execute(
                    run,compose,project,metadata,pki,identity_pki,fixtures,temp,artifacts,env) else 1
            else:results['browser-unexecuted'] = 1
            rotation_file = ROOT/'tests/p4/rotation_host.py'
            if focus in ('browser','hardening'):pass
            elif rotation_file.exists():
                results['key-rotation'] = 0 if module('p4_rotation',rotation_file).execute(
                    run,compose,project,artifacts,fixtures,env) else 1
            else:results['key-rotation-unexecuted'] = 1
        except Exception as exc:
            results['infrastructure-exception'] = 1
            print(type(exc).__name__+': '+str(exc),flush=True)
            logs = run(compose+['logs','--no-color','--tail','60'],check=False,capture_output=True,text=True)
            (artifacts/'deployment-failure.txt').write_text(logs.stdout+logs.stderr)
        finally:
            worker.close(run)
            clean = run(compose+['down','--volumes','--remove-orphans','--timeout','10'],check=False)
            results['cleanup'] = clean.returncode
            (artifacts/'commands.json').write_text(json.dumps(commands,indent=2))
            (artifacts/'run.json').write_text(json.dumps(dict(project=project,results=results,
                focus=focus,
                started_utc=started,finished_utc=datetime.now(timezone.utc).isoformat()),indent=2))
    return 0 if results and not any(results.values()) else 1


if __name__=='__main__':sys.exit(main())
