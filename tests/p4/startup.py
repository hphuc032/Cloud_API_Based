"""Same Compose dependency ordering with bounded vfs disk use on small test hosts."""
import json


def start(run,compose):
    historical=[]
    def up(*services):
        run(compose+['up','--no-deps','-d','--wait','--wait-timeout','300',*services])
    def job(service):
        run(compose+['up','--no-deps','-d',service])
        run(compose+['wait',service])
        ids=run(compose+['ps','-a','-q',service],capture_output=True,text=True).stdout.split()
        records=json.loads(run(['docker','inspect',*ids],capture_output=True,text=True).stdout)
        assert len(records)==1 and records[0]['State']['Status']=='exited' and records[0]['State']['ExitCode']==0
        historical.extend(records)
        run(compose+['rm','--force',service])
    up('postgres','identity-db')
    job('db-bootstrap');job('identity-bootstrap');job('migrate')
    up('backend','keycloak');up('identity-edge');job('kong-keys')
    up('kong','loki');up('grafana','promtail')
    return historical
