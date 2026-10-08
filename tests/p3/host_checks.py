"""Real restart persistence and identity-network isolation, confined to random project."""
import json
import time
import unittest


def execute(run, compose, project, metadata, artifacts):
    containers={c['Config']['Labels']['com.docker.compose.service']:c for c in metadata}
    image=project+'-tests'
    def output(args):return run(args,capture_output=True,text=True).stdout.strip()
    def probe(service,code):
        return output(['docker','run','--rm','--network','container:'+containers[service]['Id'],
                       '--entrypoint','python',image,'-c',code])
    def identity_command(mode):
        return output(compose+['run','--rm','--no-deps','-T','tests','python','/tests/p3/persistence.py',mode])
    class Checks(unittest.TestCase):
        def test_identity_database_private_and_persistent(self):
            db=containers['identity-db']
            self.assertFalse(db['HostConfig']['PortBindings'])
            self.assertEqual(set(db['NetworkSettings']['Networks']),{project+'_identity_data'})
            self.assertTrue(any(m['Type']=='volume' and m['Destination']=='/var/lib/postgresql/data' for m in db['Mounts']))
            self.assertFalse(containers['keycloak']['HostConfig']['PortBindings'])
            roles=output(compose+['exec','-T','identity-db','psql','-U','postgres','-d','keycloak','-Atc',
                "SELECT rolsuper,rolcreatedb,rolcreaterole,rolreplication,rolbypassrls FROM pg_roles WHERE rolname='keycloak'"])
            self.assertEqual(roles,'f|f|f|f|f')
            self.assertEqual(containers['identity-bootstrap']['State']['ExitCode'],0)
            unsafe=run(compose+['exec','-T','-e','KC_HOSTNAME=http://identity-edge:8443',
                       'keycloak','/bin/bash','/opt/p3-entrypoint.sh'],check=False,
                       capture_output=True,text=True,timeout=10)
            self.assertEqual(unsafe.returncode,1)
            self.assertIn('must be a stable HTTPS origin',unsafe.stderr)
            self.assertIn('start --import-realm',output(compose+['exec','-T','keycloak','cat','/opt/p3-entrypoint.sh']))
        def test_identity_database_inaccessible_from_other_services(self):
            ip=containers['identity-db']['NetworkSettings']['Networks'][project+'_identity_data']['IPAddress']
            code="""import socket
for host in ('identity-db', 'DBIP'):
 try:
  s=socket.create_connection((host,5432),timeout=2);s.close();raise AssertionError('identity DB reachable')
 except OSError: pass
print('blocked')
""".replace('DBIP',ip)
            for service in ('backend','kong','identity-edge','postgres','grafana'):
                self.assertEqual(probe(service,code),'blocked')
            self.assertEqual(probe('keycloak',"import socket;s=socket.create_connection(('identity-db',5432),timeout=3);s.close();print('connected')"),'connected')
        def test_restart_preserves_users_realm_and_client(self):
            self.assertEqual(identity_command('prepare'),'prepared')
            output(compose+['restart','identity-db','keycloak'])
            deadline=time.monotonic()+120
            while time.monotonic()<deadline:
                proc=run(compose+['exec','-T','keycloak','java','/opt/HealthProbe.java'],
                    check=False,capture_output=True,text=True)
                if proc.returncode==0:break
                time.sleep(2)
            self.assertEqual(proc.returncode,0)
            self.assertEqual(identity_command('verify'),'persisted: user subject, realm edit, SPA configuration, HTTPS discovery')
    result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Checks))
    (artifacts/'p3-host.json').write_text(json.dumps({'tests':result.testsRun,'failures':len(result.failures),'errors':len(result.errors)},indent=2))
    return result.wasSuccessful()
