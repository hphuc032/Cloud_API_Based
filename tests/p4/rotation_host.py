"""Stage, parse/reload, activate, retire, outage and recovery in disposable networks."""
import json,re,subprocess,time
from pathlib import Path


def execute(run,compose,project,artifacts,fixtures,env):
    results=[]
    def capture(args):
        try:return run(args,capture_output=True,text=True).stdout.strip()
        except subprocess.CalledProcessError as exc:
            diagnostic=re.sub(r'eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+','[redacted JWT]',(exc.stdout or '')+(exc.stderr or ''))
            (artifacts/'rotation-command-error.txt').write_text(diagnostic)
            # Native parser diagnostics contain configuration field errors, not
            # token material. Keep full output local for exact failure analysis.
            if 'parse' in args:
                (artifacts/'kong-candidate-parser.txt').write_text((exc.stdout or '')+(exc.stderr or ''))
            raise
    def phase(name):
        print(capture(compose+['run','--rm','--no-deps','-T','-e','PYTHONPATH=/app:/tests/p0:/tests/p3',
                              'tests','python','/tests/p4/rotation.py',name]),flush=True)
        results.append({'name':name,'status':'passed'})
    def sync():
        digest=capture(compose+['run','--rm','--no-deps','-T','kong-keys','python','-m','deployment.kong_jwks','--output','/gateway/kong.json','--candidate'])
        capture(compose+['exec','-T','kong','kong','config','parse','/gateway/kong.candidate.json'])
        capture(compose+['run','--rm','--no-deps','-T','kong-keys','python','-m','deployment.kong_jwks','--output','/gateway/kong.json','--promote-digest',digest])
        capture(compose+['exec','-T','kong','kong','reload'])
    proc=None
    try:
        # The focused runner skips browser_setup, which normally supplies the
        # reviewed customer mapping. Rotation expects an authorized customer,
        # not an unmapped identity; reuse that isolated fixture explicitly.
        if 'application_id' not in json.loads((fixtures/'identities.json').read_text()):
            capture(compose+['run','--rm','--no-deps','-T','tests','python','/tests/p4/browser_setup.py','prepare'])
        phase('stage');sync();phase('activate');phase('retire');sync()
        # Documented emergency retirement clears the backend's bounded in-process cache.
        capture(compose+['restart','backend'])
        for _ in range(30):
            if run(compose+['exec','-T','backend','python','-m','deployment.health'],check=False,capture_output=True).returncode==0:break
            time.sleep(1)
        phase('verify-retired')
        proc=subprocess.Popen(compose+['run','--rm','--no-deps','-T','tests','python','/tests/p4/outage.py'],
                             env=env,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
        for _ in range(120):
            if (fixtures/'outage-ready').exists():break
            if proc.poll() is not None:
                stdout,stderr=proc.communicate()
                diagnostic=re.sub(r'eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+','[redacted JWT]',stdout+stderr)
                (artifacts/'outage-startup-error.txt').write_text(diagnostic)
                raise AssertionError('Outage probe failed before readiness; see outage-startup-error.txt')
            time.sleep(.25)
        else:raise AssertionError('Outage probe did not become ready')
        before=capture(compose+['exec','-T','kong','sha256sum','/gateway/kong.json'])
        capture(compose+['stop','--timeout','1','identity-edge']);(fixtures/'outage-offline').touch()
        failed=run(compose+['run','--rm','--no-deps','-T','kong-keys'],check=False,capture_output=True,text=True)
        assert failed.returncode!=0
        assert capture(compose+['exec','-T','kong','sha256sum','/gateway/kong.json'])==before
        stdout,stderr=proc.communicate(timeout=100)
        if proc.returncode:raise AssertionError('Actual outage probe failed: '+stderr[-400:])
        print(stdout,flush=True);results.append({'name':'JWKS-outage-and-sync-preserves-config','status':'passed'})
        capture(compose+['up','--no-deps','-d','--wait','--wait-timeout','30','identity-edge']);sync()
        time.sleep(5.1)  # the defined backend failure/unknown-key refresh backoff
        phase('verify-retired')
        return True
    except Exception as exc:
        results.append({'name':'rotation-or-outage','status':'failed','error':type(exc).__name__+': '+str(exc)})
        print('Rotation/outage validation failed: '+type(exc).__name__,flush=True)
        return False
    finally:
        if proc and proc.poll() is None:proc.terminate();proc.communicate(timeout=10)
        run(compose+['up','--no-deps','-d','--wait','--wait-timeout','30','identity-edge'],check=False,capture_output=True)
        (artifacts/'key-rotation-results.json').write_text(json.dumps(results,indent=2))
