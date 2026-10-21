"""P4-specific memberships preserve P1 private data and P2 transport boundaries."""
import json
import unittest


def execute(run,compose,project,metadata,artifacts,collector="promtail"):
    containers={c['Config']['Labels']['com.docker.compose.service']:c for c in metadata}
    def output(args):return run(args,capture_output=True,text=True).stdout.strip()
    def probe(service,code):
        return output(['docker','run','--rm','--network','container:'+containers[service]['Id'],
                       '--entrypoint','python',project+'-tests','-c',code])
    class Checks(unittest.TestCase):
        def test_networks_and_no_public_databases_or_admin(self):
            expected={'postgres':{'app_data'},'backend':{'api_transport','app_data','oidc_transport'},
                      'kong':{'edge','api_transport'},'identity-db':{'identity_data'},
                      'keycloak':{'identity_data','identity_transport'},
                      'identity-edge':{'identity_transport','oidc_transport'},'kong-keys':{'oidc_transport'}}
            for service,names in expected.items():
                self.assertEqual(set(containers[service]['NetworkSettings']['Networks']),{project+'_'+n for n in names})
            for name in ('app_data','identity_data','observability'):
                self.assertTrue(json.loads(output(['docker','network','inspect',project+'_'+name]))[0]['Internal'])
            for service in ('postgres','identity-db','backend','keycloak','identity-edge'):
                self.assertFalse(containers[service]['HostConfig']['PortBindings'])
            self.assertEqual(containers['kong']['Config']['Env'].count('KONG_ADMIN_LISTEN=off'),1)
        def test_private_database_unreachable_by_gateway_and_identity_edge(self):
            for db,network in [('postgres','app_data'),('identity-db','identity_data')]:
                ip=containers[db]['NetworkSettings']['Networks'][project+'_'+network]['IPAddress']
                code="import socket\nfor host in "+repr((db,ip))+":\n try:\n  socket.create_connection((host,5432),2);raise AssertionError('Private database reachable')\n except OSError:pass\nprint('blocked')"
                for service in ('kong','identity-edge'):self.assertEqual(probe(service,code),'blocked')
        def test_database_roles_and_mapping_read_privilege(self):
            for db,role in [('postgres','app_runtime'),('postgres','app_migrator'),('identity-db','keycloak')]:
                sql="SELECT rolsuper,rolcreatedb,rolcreaterole,rolreplication,rolbypassrls FROM pg_roles WHERE rolname='"+role+"'"
                self.assertEqual(output(compose+['exec','-T',db,'psql','-U','postgres','-Atc',sql]),'f|f|f|f|f')
            sql="SELECT has_table_privilege('app_runtime','external_identities','SELECT'),has_table_privilege('app_runtime','external_identities','INSERT'),has_table_privilege('app_runtime','external_identities','UPDATE'),has_table_privilege('app_runtime','external_identities','DELETE')"
            self.assertEqual(output(compose+['exec','-T','postgres','psql','-U','postgres','-d','p0_baseline','-Atc',sql]),'t|f|f|f')
        def test_no_socket_privileged_container_or_secret_key_volume(self):
            for c in containers.values():
                self.assertFalse(c['HostConfig']['Privileged'])
                self.assertFalse(any('docker.sock' in m['Destination'] for m in c['Mounts']))
            self.assertEqual(output(compose+['exec','-T','kong','sh','-c',"grep -c 'PRIVATE KEY' /gateway/kong.json || true"]),'0')
        def test_observability_ingests_backend_logs(self):
            code="""import json,time,urllib.request,urllib.parse
assert urllib.request.urlopen('COLLECTOR_READY',timeout=5).status==200
assert urllib.request.urlopen('http://grafana:3000/api/health',timeout=5).status==200
query=urllib.parse.urlencode({'query':'{service="backend"}','limit':'1'})
for _ in range(30):
 data=json.load(urllib.request.urlopen('http://loki:3100/loki/api/v1/query_range?'+query,timeout=5))
 if data['data']['result']:print('ingested');break
 time.sleep(1)
else:raise AssertionError('Backend logs not ingested')
"""
            code=code.replace('COLLECTOR_READY','http://alloy:12345/-/ready' if collector=='alloy' else 'http://promtail:9080/ready')
            self.assertEqual(probe('loki',code),'ingested')
    result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Checks))
    (artifacts/'p4-host.json').write_text(json.dumps({'tests':result.testsRun,'failures':len(result.failures),'errors':len(result.errors)},indent=2))
    return result.wasSuccessful()
