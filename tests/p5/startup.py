"""Same Compose dependency ordering with bounded vfs disk use on small test hosts."""
import json,os


def start(run,compose):
    historical=[]
    def up(*services):
        run(compose+['up','--no-deps','-d','--wait','--wait-timeout','300',*services])
    def job(service):
        run(compose+['up','--no-deps','-d',service])
        # Wait on the exact ID, including jobs which have already exited.
        job_ids=run(compose+['ps','-a','-q',service],capture_output=True,text=True).stdout.split()
        assert len(job_ids)==1
        status=run(['docker','wait',job_ids[0]],capture_output=True,text=True).stdout.strip()
        assert status=='0', f'{service} exited {status}'
        ids=run(compose+['ps','-a','-q',service],capture_output=True,text=True).stdout.split()
        records=json.loads(run(['docker','inspect',*ids],capture_output=True,text=True).stdout)
        assert len(records)==1 and records[0]['State']['Status']=='exited' and records[0]['State']['ExitCode']==0
        historical.extend(records)
        run(compose+['rm','--force',service])
    up('postgres','identity-db')
    job('db-bootstrap');job('identity-bootstrap');job('migrate')
    up('backend','keycloak');up('identity-edge');job('kong-keys')
    up('kong')
    if not os.environ.get('P5_CORE_ONLY'):
        up('loki');up('grafana','promtail')
    return historical
