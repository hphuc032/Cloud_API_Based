"""Real controls -> Docker files -> Alloy -> Loki -> provisioned Grafana."""
import json,os,time,secrets
from pathlib import Path
from uuid import UUID,uuid4
import httpx,psycopg2,pytest
from transport import http_client
from test_cutover import headers,tokens,client,backend,identity,admin,oidc_user,legacy_order,signed as token_signed
from test_hardening import signed,raw,envelope


def query(expr):
 with httpx.Client(trust_env=False,timeout=10) as c:
  r=c.get('http://loki:3100/loki/api/v1/query_range',params={'query':expr,'limit':5000,'since':'10m'})
  assert r.status_code==200,r.text
  return [json.loads(v[1]) for stream in r.json()['data']['result'] for v in stream['values']]


def ingested(service,event,rid=None):
 expr='{service="'+service+'"} | json | event_type="'+event+'"'
 if rid:expr+=' | request_id="'+rid+'"'
 for _ in range(30):
  rows=query(expr)
  if rows:
   path=Path('/results/p6-ingestion.json')
   previous=json.loads(path.read_text()) if path.exists() else []
   previous.append({'service':service,'event_type':event,'request_id':rid,'samples':rows[:2]})
   path.write_text(json.dumps(previous,indent=2))
   return rows
  time.sleep(1)
 raise AssertionError('No real ingestion for '+service+'/'+event)


def test_gateway_boundary_and_sensitive_query():
 canary='p6-secret-'+secrets.token_hex(12)
 with http_client('https://kong:8443') as c:
  r=c.get('/api/v1/auth/me?code='+canary,headers={'X-Request-ID':'forged-'+canary,'Authorization':'Bearer '+canary,'Cookie':'session='+canary})
 assert r.status_code==401
 rid=r.headers['x-request-id'];assert UUID(rid).version==4 and canary not in rid
 rows=ingested('kong','token_rejected',rid)
 assert all(canary not in json.dumps(row) for row in rows)
 assert not query('{service=~".+"} |= "'+canary+'"')
 assert not query('{service="backend"} | json | request_id="'+rid+'"')


def test_success_correlation():
 sent=str(uuid4())
 with http_client('https://kong:8443') as c:r=c.get('/health',headers={'X-Request-ID':sent})
 assert r.status_code==200
 rid=r.headers['x-request-id'];assert rid!=sent
 assert ingested('kong','http_request',rid)
 assert ingested('backend','http_request',rid)


@pytest.mark.parametrize('change',[{'aud':'wrong'},{'iss':'https://evil.example/realms/no'}])
def test_wrong_claims_ingestion(client,headers,tokens,change):
 headers('customer')
 r=client.get('/api/v1/auth/me',headers={'Authorization':'Bearer '+token_signed(tokens['customer']['access_token'],change)})
 assert r.status_code==401
 assert ingested('backend','token_rejected',r.headers['x-request-id'])


def test_admin_denial(client,headers):
 r=client.get('/api/v1/users/',headers=headers('customer'))
 assert r.status_code==403
 assert ingested('backend','rbac_denied',r.headers['x-request-id'])


def test_bola_denial(client,headers,legacy_order):
 r=client.get('/api/v1/orders/'+legacy_order,headers=headers('customer_b'))
 assert r.status_code==403
 assert ingested('backend','ownership_denied',r.headers['x-request-id'])


def test_webhook_signatures_retry_conflict():
 with http_client('https://kong:8443') as c:
  body=raw(envelope());h=signed(body)
  missing=c.post('/api/v1/webhooks/receive',content=body,headers={'Content-Type':'application/json'})
  assert missing.status_code==401
  rid=missing.headers['x-request-id']
  ingested('backend','webhook_rejected',rid)
  ingested('kong','http_request',rid)
  assert not query('{service="kong"} | json | event_type="token_rejected" | request_id="'+rid+'"')
  r=c.post('/api/v1/webhooks/receive',content=body,headers={**h,'X-Signature':'sha256='+'0'*64})
  assert r.status_code==403;ingested('backend','webhook_rejected',r.headers['x-request-id'])
  assert c.post('/api/v1/webhooks/receive',content=body,headers=h).status_code==200
  r=c.post('/api/v1/webhooks/receive',content=body,headers=h)
  assert r.status_code==200 and r.headers['x-webhook-replayed']=='true'
  ingested('backend','webhook_replayed',r.headers['x-request-id'])
  changed=json.loads(body);changed['order_id']='different';body=raw(changed)
  r=c.post('/api/v1/webhooks/receive',content=body,headers=signed(body))
  assert r.status_code==409;ingested('backend','webhook_conflict',r.headers['x-request-id'])


@pytest.mark.parametrize('url',['http://127.0.0.1','http://10.0.0.1','http://169.254.169.254'])
def test_ssrf_telemetry(client,headers,url):
 r=client.post('/api/v1/security/fetch-url',json={'url':url},headers=headers('staff'))
 assert r.status_code in (400,403)
 ingested('backend','ssrf_denied',r.headers['x-request-id'])


def test_validation_redaction(client,headers):
 canary='p6-body-'+secrets.token_hex(12)
 r=client.post('/api/v1/products/',json={'name':canary,'price':None,'password':canary},headers=headers('staff'))
 assert r.status_code==422
 rows=ingested('backend','validation_failed',r.headers['x-request-id'])
 assert canary not in json.dumps(rows)
 assert rows[0]['route']=='/api/v1/products/'


def test_audit_transaction_and_privileges(client,headers,users):
 r=client.patch('/api/v1/users/'+str(users['customer'].id),json={'is_verified':True},headers=headers('admin'))
 assert r.status_code==200
 with psycopg2.connect(os.environ['P0_ADMIN_DATABASE_URL']) as conn,conn.cursor() as cur:
  cur.execute("SELECT action,user_id,request_id,detail FROM audit_logs WHERE request_id=%s",(r.headers['x-request-id'],));row=cur.fetchone()
  assert row and row[0]=='user_updated' and str(row[1])==str(users['admin'].id)
  assert row[3]=={'schema_version':1}
  cur.execute("SELECT has_table_privilege('app_runtime','audit_logs',x) FROM unnest(ARRAY['INSERT','SELECT','UPDATE','DELETE']) x")
  assert [x[0] for x in cur.fetchall()]==[True,False,False,False]
 from app.middleware.logging import audit
 from app.database.session import SessionLocal
 from sqlalchemy import text
 db=SessionLocal()
 audit(db,users['admin'].id,'rollback_probe','user',users['customer'].id)
 db.flush();db.rollback();db.close()
 with psycopg2.connect(os.environ['P0_ADMIN_DATABASE_URL']) as conn,conn.cursor() as cur:
  cur.execute("SELECT count(*) FROM audit_logs WHERE action='rollback_probe'");assert cur.fetchone()[0]==0


def grafana():
 return httpx.Client(base_url='http://grafana:3000',auth=('admin',Path('/run/secrets/grafana_admin_password').read_text().strip()),trust_env=False,timeout=10)


def test_grafana_dashboards_queries_and_rules():
 with httpx.Client(trust_env=False) as lc:
  response=lc.get('http://loki:3100/loki/api/v1/labels');assert response.status_code==200
  labels=response.json()['data'];assert set(labels)<={'service','project'}, labels
 with grafana() as c:
  for uid in ('overview','identity','attacks','infrastructure'):
   r=c.get('/api/dashboards/uid/florasecure-'+uid);assert r.status_code==200,r.text
   for panel in r.json()['dashboard']['panels']:
    for target in panel.get('targets',[]):
     expr=target['expr'].replace('$__interval','1m')
     with httpx.Client(trust_env=False) as lc:
      response=lc.get('http://loki:3100/loki/api/v1/query',params={'query':expr});assert response.status_code==200,response.text
  r=c.get('/api/v1/provisioning/alert-rules');assert r.status_code==200
  assert len(r.json())==6
  for rule in r.json():assert rule['noDataState']=='NoData' and rule['execErrState']=='Error'


def test_keycloak_login_failure_collected(identity,admin,oidc_user):
 from test_gateway import test_keycloak_repeated_wrong_password_is_temporarily_disabled as exercise
 exercise(identity,admin,oidc_user)
 rows=ingested('keycloak','login_failed')
 assert set(rows[0])=={'service','event_type','status_code'}


def test_gateway_rate_limit_collected():
 from test_gateway import test_pre_auth_throttle_rejects_forwarding_header_spoofing as exercise
 exercise()
 ingested('kong','rate_limited')


def rule_state(c):
 r=c.get('/api/prometheus/grafana/api/v1/rules');assert r.status_code==200,r.text
 for group in r.json()['data']['groups']:
  for rule in group['rules']:
   if rule.get('name')=='P6 jwt-rejections':return rule
 raise AssertionError('Provisioned rule absent from engine')


def test_actual_grafana_engine_firing_and_recovery():
 # Begin from a neutral real rule state; stale previous-window traffic must not
 # substitute for a measured threshold transition.
 with grafana() as gc:
  for _ in range(45):
   before=rule_state(gc)
   if before.get('state')=='inactive':break
   time.sleep(2)
  else:raise AssertionError('Rule did not reach neutral state before experiment')
 # Real gateway rejections, no direct Loki push or fabricated dashboard series.
 with http_client('https://kong:8443') as c:
  for _ in range(10):assert c.get('/api/v1/auth/me').status_code==401
 ingested('kong','token_rejected')
 snapshots=[]
 with grafana() as c:
  for _ in range(28):
   state=rule_state(c);snapshots.append({'state':state.get('state'),'health':state.get('health')})
   if state.get('state')=='firing':break
   time.sleep(2)
  else:raise AssertionError('Actual rule did not fire: '+json.dumps(snapshots))
  for _ in range(45):
   state=rule_state(c);snapshots.append({'state':state.get('state'),'health':state.get('health')})
   if state.get('state')=='inactive':break
   time.sleep(2)
  else:raise AssertionError('Actual rule did not recover: '+json.dumps(snapshots))
 Path('/results/p6-alert-evaluation.json').write_text(json.dumps({'rule':'p6-jwt-rejections','actual_engine':True,'initial_state':'inactive','external_delivery_tested':False,'states':snapshots},indent=2))


def test_ssrf_rbac_is_not_destination_denial(client,headers):
 r=client.post('/api/v1/security/fetch-url',json={'url':'http://127.0.0.1'},headers=headers('customer'))
 assert r.status_code==403
 rid=r.headers['x-request-id']
 ingested('backend','rbac_denied',rid)
 assert not query('{service="backend"} | json | event_type="ssrf_denied" | request_id="'+rid+'"')


def test_product_and_order_audit_commits(client,headers,product,legacy_order,users):
 operations=[]
 r=client.post('/api/v1/products/',json={'sku':'P6-AUDIT-'+uuid4().hex,'name':'Audit fixture','price':9},headers=headers('staff'))
 assert r.status_code==201
 pid=r.json()['id'];operations.append((r,'product_created',pid))
 r=client.patch('/api/v1/products/'+pid,json={'price':10},headers=headers('staff'));assert r.status_code==200
 operations.append((r,'product_updated',pid))
 r=client.delete('/api/v1/products/'+pid,headers=headers('staff'));assert r.status_code==204
 operations.append((r,'product_deactivated',pid))
 r=client.patch('/api/v1/orders/'+legacy_order+'/status',json={'status':'shipped'},headers=headers('staff'));assert r.status_code==200
 operations.append((r,'order_status_updated',legacy_order))
 with psycopg2.connect(os.environ['P0_ADMIN_DATABASE_URL']) as conn,conn.cursor() as cur:
  for response,action,resource in operations:
   cur.execute('SELECT action,user_id,resource_id FROM audit_logs WHERE request_id=%s',(response.headers['x-request-id'],))
   rows=cur.fetchall();assert len(rows)==1
   assert rows[0][0]==action and str(rows[0][1])==str(users['staff'].id) and str(rows[0][2])==resource


@pytest.mark.parametrize('change',[{'role':'staff'},{'is_active':False}])
def test_role_and_activation_audit(client,headers,users,change):
 r=client.patch('/api/v1/users/'+str(users['customer'].id),json=change,headers=headers('admin'));assert r.status_code==200
 with psycopg2.connect(os.environ['P0_ADMIN_DATABASE_URL']) as conn,conn.cursor() as cur:
  cur.execute('SELECT action,user_id,resource_id FROM audit_logs WHERE request_id=%s',(r.headers['x-request-id'],))
  row=cur.fetchone();assert row and row[0]=='user_updated' and str(row[1])==str(users['admin'].id) and str(row[2])==str(users['customer'].id)


def test_settings_errors_and_repr_do_not_echo_credentials():
 from app.config import Settings,settings
 from pydantic import ValidationError
 secret='p6-sensitive-'+secrets.token_hex(20)
 values={'DATABASE_URL':settings.DATABASE_URL,'SECRET_KEY':secret,'WEBHOOK_SECRET':secret,
         'AUTH_MODE':'oidc','OIDC_ISSUER':'http://invalid.example/realms/invalid'}
 with pytest.raises(ValidationError) as captured:Settings(_env_file=None,**values)
 assert secret not in str(captured.value) and settings.DATABASE_URL not in str(captured.value)
 values.update(AUTH_MODE='legacy',OIDC_ISSUER=None)
 configured=Settings(_env_file=None,**values)
 assert secret not in repr(configured) and settings.DATABASE_URL not in repr(configured)


@pytest.mark.parametrize('kind',['unmapped','disabled'])
def test_identity_mapping_rejection_collected(client,tokens,users,db,kind):
 if kind=='disabled':
  from test_cutover import FIXTURES,ISSUER
  from deployment.identity_mapping import bind
  with psycopg2.connect(os.environ['P0_ADMIN_DATABASE_URL']) as conn:
   bind(conn,trusted_issuer=ISSUER,issuer=ISSUER,subject=FIXTURES['users']['customer']['subject'],
        user_id=users['customer'].id,reviewed_by='disposable-operator',review_reference='P6-disabled-account-log')
  users['customer'].is_active=False;db.commit()
 r=client.get('/api/v1/auth/me',headers={'Authorization':'Bearer '+tokens['customer']['access_token']})
 assert r.status_code==401
 rows=ingested('backend','identity_unmapped_or_disabled',r.headers['x-request-id'])
 assert all(not {'sub','email','password','authorization','user_id'} & row.keys() for row in rows)


def test_four_additional_rule_transitions(backend,headers,legacy_order):
 from alert_recovery import observe,query_values,save
 uids=['p6-webhook-attacks','p6-ownership-denials','p6-ssrf-denials','p6-rate-limits']
 with grafana() as gc:
  initial=observe(gc,uids,'inactive')
  # Use actual enrolled mTLS for backend events, preserving all auth decisions.
  staff=headers('staff');customer=headers('customer_b')
  # Align a fresh fixed window without altering counters or rate policies.
  time.sleep(61-int(time.time())%60)
  with http_client('https://kong:8443') as c:
   for _ in range(60):assert c.get('/api/v1/users/').status_code==401
   for _ in range(12):assert c.get('/api/v1/users/').status_code==429
  rids=[]
  for _ in range(8):
   body=raw(envelope());r=backend.post('/api/v1/webhooks/receive',content=body,headers={'Content-Type':'application/json'})
   assert r.status_code==401;rids.append(('webhook_rejected',r.headers['x-request-id']))
   r=backend.get('/api/v1/orders/'+legacy_order,headers=customer)
   assert r.status_code==403;rids.append(('ownership_denied',r.headers['x-request-id']))
   r=backend.post('/api/v1/security/fetch-url',headers=staff,json={'url':'http://127.0.0.1'})
   assert r.status_code==403;rids.append(('ssrf_denied',r.headers['x-request-id']))
  body=raw(envelope())
  assert backend.post('/api/v1/webhooks/receive',content=body,headers=signed(body)).status_code==200
  changed=json.loads(body);changed['order_id']='different';body=raw(changed)
  r=backend.post('/api/v1/webhooks/receive',content=body,headers=signed(body));assert r.status_code==409
  rids.append(('webhook_conflict',r.headers['x-request-id']))
  for event,rid in rids:ingested('backend',event,rid)
  ingested('kong','rate_limited')
  values=query_values(gc,uids)
  firing=observe(gc,uids,'firing',65)
  recovery=observe(gc,uids,'inactive',110)
  data={'passed':True,'external_delivery_tested':False,'initial':initial,'queries':values,'firing':firing,'recovery':recovery,'real_request_ids':rids}
  for uid in uids:
   assert any(s['rules'][uid]['state']=='pending' for s in firing),(uid,'No pending state observed')
  save('four-rules',data)
