"""Actual Keycloak JWKS, Kong RS256 gateway, backend mTLS, and PostgreSQL authority."""
import copy,json,os,time,secrets
from pathlib import Path
from uuid import uuid4
import httpx,psycopg2,pytest
from jose import jwt
from transport import http_client
from deployment.identity_mapping import bind
from deployment.identity_review import review,apply
from test_identity import (identity,admin,oidc_user,authorize,exchange,discovery,
 test_discovery_jwks_verified_https,test_wrong_pkce_verifier_rejected,test_invalid_redirect_not_followed,
 test_pkce_s256_required,test_password_grant_disabled,test_implicit_and_hybrid_disabled,
 test_public_edge_denies_admin_and_master,test_duplicate_or_conflicting_mappings_rejected,
 test_unknown_user_and_untrusted_issuer_rejected,test_email_collision_never_links_or_creates_mapping,
 )
from test_authorization import (test_product_crud_authorization,test_order_create_authorization_and_server_ownership,
 test_order_list_read_status_authorization,test_user_self_vs_admin_authorization,
 test_admin_self_protection_and_db_role_active_authority,test_invalid_orders_do_not_deduct_stock,
 test_current_order_status_policy,test_defect_product_null_field,test_defect_user_null_field)
from test_webhook_ssrf import test_webhook_hmac_timestamp,test_webhook_debug_helper_disabled,test_defect_webhook_json_shape,test_defect_webhook_replay
from test_https_business import test_https_ssrf_uses_real_dns_and_preserves_roles,test_https_ssrf_denies_invalid_targets,PacedClient

ISSUER=os.environ['OIDC_ISSUER'];FIXTURES=json.loads(Path('/test-fixtures/identities.json').read_text())
PRIVATE=Path('/test-fixtures/signing.key').read_text()

@pytest.fixture
def admin(identity):
 # Master admin access tokens expire quickly; no module-lived stale credential.
 r=identity.post('https://keycloak:8443/realms/master/protocol/openid-connect/token',data={
  'grant_type':'password','client_id':'admin-cli','username':'admin',
  'password':Path('/run/secrets/keycloak_admin_password').read_text().strip()})
 assert r.status_code==200
 return {'Authorization':'Bearer '+r.json()['access_token']}

@pytest.fixture
def client():
 with http_client('https://kong:8443') as c:yield PacedClient(c)

@pytest.fixture
def tokens(identity):
 data=FIXTURES['users']
 for u in data.values():
  if jwt.get_unverified_claims(u['tokens']['access_token'])['exp']<time.time()+60:
   code,verifier,_=authorize(identity,u['username'],u['password']);r=exchange(identity,code,verifier);assert r.status_code==200;u['tokens']=r.json()
 return {role:u['tokens'] for role,u in data.items()}

@pytest.fixture
def headers(users,tokens):
 with psycopg2.connect(os.environ['P0_ADMIN_DATABASE_URL']) as conn:
  for role,u in FIXTURES['users'].items():
   bind(conn,trusted_issuer=ISSUER,issuer=ISSUER,subject=u['subject'],user_id=users[role].id,
        reviewed_by='disposable-operator',review_reference='P4-explicit-fixture-review')
 return lambda role:{'Authorization':'Bearer '+tokens[role]['access_token']} if role!='anonymous' else {}

@pytest.fixture
def backend():
 with http_client('https://backend:8443',backend=True) as c:yield c

@pytest.fixture
def legacy_order(users,product):
 # Historical application row predates identity binding; no token/auto-link fixture.
 oid=str(uuid4())
 with psycopg2.connect(os.environ['P0_ADMIN_DATABASE_URL']) as conn,conn.cursor() as cur:
  cur.execute('INSERT INTO orders(id,user_id,order_number,total_amount) VALUES (%s,%s,%s,25)',
   (oid,str(users['customer'].id),'P4-HISTORY-'+uuid4().hex))
  cur.execute('INSERT INTO order_items(order_id,product_id,quantity,unit_price) VALUES (%s,%s,2,12.5)',(oid,str(product.id)))
 return oid


def signed(token,changes=None,drop=(),header_changes=None):
 claims=jwt.get_unverified_claims(token);claims.update(changes or {})
 for field in drop:claims.pop(field,None)
 header=jwt.get_unverified_header(token);header.update(header_changes or {})
 return jwt.encode(claims,PRIVATE,algorithm='RS256',headers=header)


def test_real_access_and_legacy_rejection(client,backend,headers,tokens,users):
 assert client.get('/api/v1/auth/me',headers=headers('customer')).json()['id']==str(users['customer'].id)
 assert backend.get('/api/v1/auth/me',headers=headers('customer')).json()['id']==str(users['customer'].id)
 from app.auth.security import create_access_token
 legacy=create_access_token({'sub':str(users['customer'].id),'role':'admin'})
 for c in (client,backend):assert c.get('/api/v1/auth/me',headers={'Authorization':'Bearer '+legacy}).status_code==401


@pytest.mark.parametrize('changes,drop',[
 ({'iss':'https://evil.example/realms/florasecure'},()),({'aud':'wrong'},()),({'typ':'ID'},()),
 ({'typ':'Refresh'},()),({'azp':'other-client'},()),({},('exp',)),({},('iat',)),({},('sub',)),
 ({'sub':[]},()),({'sub':''},()),({'sub':'not-a-UUID'},()),({'sub':'\x00'},()),({},('aud',)),({},('iss',)),
 ({'exp':int(time.time())-1,'iat':int(time.time())-10},()),
 ({'nbf':int(time.time())+1000},()),({'iat':int(time.time())+600,'exp':int(time.time())+900},()),
 ({'exp':int(time.time())+3600},()),
])
def test_backend_independent_claim_validation(backend,headers,tokens,changes,drop):
 headers('customer');token=signed(tokens['customer']['access_token'],changes,drop)
 assert backend.get('/api/v1/auth/me',headers={'Authorization':'Bearer '+token}).status_code==401


@pytest.mark.parametrize('kind',['missing','garbage','invalid-signature','unknown-kid','missing-exp','expired','hs256','id-token','refresh-token'])
def test_gateway_rejects_or_backend_finishes_validation(client,backend,headers,tokens,kind):
 headers('customer');token=tokens['customer']['access_token'];gateway_expected=True
 if kind=='missing':h={}
 else:
  if kind=='garbage':token='not-a-token'
  elif kind=='invalid-signature':
   from cryptography.hazmat.primitives.asymmetric import rsa
   from cryptography.hazmat.primitives import serialization
   key=rsa.generate_private_key(public_exponent=65537,key_size=2048).private_bytes(serialization.Encoding.PEM,serialization.PrivateFormat.PKCS8,serialization.NoEncryption())
   token=jwt.encode(jwt.get_unverified_claims(token),key,algorithm='RS256',headers=jwt.get_unverified_header(token))
  elif kind=='unknown-kid':token=signed(token,header_changes={'kid':'unrecognized-key'})
  elif kind=='missing-exp':token=signed(token,drop=['exp'])
  elif kind=='expired':token=signed(token,{'exp':int(time.time())-1,'iat':int(time.time())-10})
  elif kind=='hs256':token=jwt.encode(jwt.get_unverified_claims(token),secrets.token_urlsafe(32),algorithm='HS256',headers={'kid':jwt.get_unverified_header(token)['kid']})
  elif kind in ('id-token','refresh-token'):
   token=tokens['customer']['id_token' if kind=='id-token' else 'refresh_token'];gateway_expected=False
  h={'Authorization':'Bearer '+token}
 r=client.get('/api/v1/auth/me',headers=h);assert r.status_code==401
 if gateway_expected:assert 'x-kong-upstream-latency' not in r.headers
 assert backend.get('/api/v1/auth/me',headers=h).status_code==401


def test_wrong_audience_issuer_type_gateway_is_not_oidc(client,headers,tokens):
 headers('customer')
 for change in [{'aud':'other'},{'iss':'https://evil.example/realms/florasecure'},{'typ':'ID'},{'nbf':int(time.time())+300}]:
  r=client.get('/api/v1/auth/me',headers={'Authorization':'Bearer '+signed(tokens['customer']['access_token'],change)})
  assert r.status_code==401 and 'x-kong-upstream-latency' in r.headers


def test_claim_roles_headers_cannot_elevate(client,headers,tokens,users,db):
 h=headers('customer');h.update({'X-User-Id':str(users['admin'].id),'X-User-Role':'admin','X-Consumer-Username':'admin'})
 h['Authorization']='Bearer '+signed(tokens['customer']['access_token'],{'role':'admin','realm_access':{'roles':['admin']}})
 assert client.get('/api/v1/users/',headers=h).status_code==403
 assert client.get('/api/v1/auth/me',headers=h).json()['id']==str(users['customer'].id)
 users['customer'].is_active=False;db.commit()
 assert client.get('/api/v1/auth/me',headers=h).status_code==401


def test_unmapped_identity_email_collision_denied(client,tokens,users):
 assert client.get('/api/v1/auth/me',headers={'Authorization':'Bearer '+tokens['customer']['access_token']}).status_code==401
 with psycopg2.connect(os.environ['P0_ADMIN_DATABASE_URL']) as conn,conn.cursor() as cur:
  cur.execute('SELECT count(*) FROM external_identities');assert cur.fetchone()[0]==0


@pytest.mark.parametrize('path',['login','register','refresh','logout'])
def test_retired_local_issuance(client,backend,path):
 for c in (client,backend):assert c.post('/api/v1/auth/'+path,json={}).status_code==410


def test_public_routes_and_cors(client):
 assert client.get('/api/v1/products/').status_code==200
 assert client.get('/health').status_code==200
 assert client.get('/api/v1/users/').status_code==401
 allowed=client.options('/api/v1/orders/',headers={'Origin':'https://localhost:5174','Access-Control-Request-Method':'POST','Access-Control-Request-Headers':'authorization,content-type'})
 assert allowed.status_code in (200,204) and allowed.headers['access-control-allow-origin']=='https://localhost:5174'
 denied=client.options('/api/v1/orders/',headers={'Origin':'https://evil.example','Access-Control-Request-Method':'POST'})
 assert denied.headers.get('access-control-allow-origin')!='https://evil.example'


def test_mapping_runtime_select_only():
 with psycopg2.connect(os.environ['DATABASE_URL']) as conn,conn.cursor() as cur:
  cur.execute('SELECT count(*) FROM external_identities');assert cur.fetchone()[0]>=0
  for sql in ['DELETE FROM external_identities',"INSERT INTO external_identities(issuer,subject,user_id,reviewed_by,review_reference) VALUES ('https://id.example/realms/x','x',gen_random_uuid(),'x','x')",'UPDATE external_identities SET subject=subject']:
   with pytest.raises(psycopg2.errors.InsufficientPrivilege):cur.execute(sql)
   conn.rollback()


def test_reviewed_dry_run_approval_existing_ids(users,legacy_order):
 manifest=[{'subject':'operator-reviewed','user_id':str(users['customer'].id),'reviewed_by':'test-operator','review_reference':'P4-approval'}]
 with psycopg2.connect(os.environ['P0_ADMIN_DATABASE_URL']) as conn:
  report,digest=review(conn,ISSUER,manifest)
  with conn.cursor() as cur:cur.execute('SELECT count(*) FROM external_identities');assert cur.fetchone()[0]==0
  with pytest.raises(ValueError):apply(conn,ISSUER,manifest,'unapproved')
  conn.rollback();assert apply(conn,ISSUER,manifest,digest)==1
  with conn.cursor() as cur:
   cur.execute('SELECT o.id,e.user_id FROM orders o JOIN external_identities e ON o.user_id=e.user_id WHERE o.id=%s',(legacy_order,))
   oid,uid=cur.fetchone();assert str(oid)==legacy_order and str(uid)==str(users['customer'].id)


def test_mapping_preserves_ids_orders_and_roles(users,orders):
 with psycopg2.connect(os.environ['P0_ADMIN_DATABASE_URL']) as conn,conn.cursor() as cur:
  for role in ['customer','customer_b']:
   cur.execute('SELECT o.id,o.user_id,e.subject,u.role FROM orders o JOIN users u ON u.id=o.user_id JOIN external_identities e ON e.user_id=u.id AND e.issuer=%s WHERE o.id=%s',(ISSUER,orders[role]))
   oid,uid,subject,dbrole=cur.fetchone()
   assert str(oid)==orders[role] and str(uid)==str(users[role].id)
   assert subject==FIXTURES['users'][role]['subject'] and dbrole=='customer'


def test_new_customer_review_and_collision(users):
 with psycopg2.connect(os.environ['P0_ADMIN_DATABASE_URL']) as conn:
  manifest=[{'subject':'new-sub','email':users['customer'].email,'username':'new-user','reviewed_by':'operator','review_reference':'review'}]
  with pytest.raises(ValueError):review(conn,ISSUER,manifest)
  manifest[0]['email']=uuid4().hex+'@example.com';manifest[0]['username']=uuid4().hex
  _,digest=review(conn,ISSUER,manifest);assert apply(conn,ISSUER,manifest,digest)==1
  with conn.cursor() as cur:
   cur.execute('SELECT u.role,u.id FROM users u JOIN external_identities e ON u.id=e.user_id WHERE e.subject=%s',('new-sub',))
   role,uid=cur.fetchone();assert role=='customer' and str(uid) not in [str(u.id) for u in users.values()]


def test_refresh_logout_and_expiration(identity,oidc_user):
 u,p,_=oidc_user;code,verifier,_=authorize(identity,u,p);r=exchange(identity,code,verifier);assert r.status_code==200
 token=r.json();r=identity.post(ISSUER+'/protocol/openid-connect/token',data={'grant_type':'refresh_token','client_id':'florasecure-spa','refresh_token':token['refresh_token']});assert r.status_code==200
 newer=r.json();assert identity.post(ISSUER+'/protocol/openid-connect/token',data={'grant_type':'refresh_token','client_id':'florasecure-spa','refresh_token':token['refresh_token']}).status_code==400
 # Replay can revoke a client session. Start a fresh session for logout validation.
 code,verifier,_=authorize(identity,u,p);token=exchange(identity,code,verifier).json()
 assert identity.post(ISSUER+'/protocol/openid-connect/logout',data={'client_id':'florasecure-spa','refresh_token':token['refresh_token']}).status_code==204
 assert identity.post(ISSUER+'/protocol/openid-connect/token',data={'client_id':'florasecure-spa','grant_type':'refresh_token','refresh_token':token['refresh_token']}).status_code==400


def test_p4_realm_client_reproducibility(identity,admin):
 source=json.loads(Path('/realm-p4.json').read_text())
 actual=identity.get('https://keycloak:8443/admin/realms/florasecure',headers=admin).json()
 for field in ['registrationAllowed','revokeRefreshToken','refreshTokenMaxReuse','accessTokenLifespan','ssoSessionIdleTimeout','ssoSessionMaxLifespan','defaultSignatureAlgorithm']:
  assert actual[field]==source[field]
 client=identity.get('https://keycloak:8443/admin/realms/florasecure/clients',headers=admin,params={'clientId':'florasecure-spa'}).json()[0]
 expected=source['clients'][0]
 for field in ['publicClient','standardFlowEnabled','implicitFlowEnabled','directAccessGrantsEnabled','serviceAccountsEnabled']:
  assert client[field]==expected[field]
 # Keycloak serializes URI policy sets in a different order after persistence.
 for field in ['redirectUris','webOrigins']:
  assert set(client[field])==set(expected[field]) and len(client[field])==len(expected[field])
 for field in ['pkce.code.challenge.method','post.logout.redirect.uris']:
  assert client['attributes'][field]==expected['attributes'][field]


def test_review_rejects_ambiguous_batch_and_privileged_provisioning(users):
 common={'email':uuid4().hex+'@example.com','username':uuid4().hex,'reviewed_by':'operator','review_reference':'review'}
 with psycopg2.connect(os.environ['P0_ADMIN_DATABASE_URL']) as conn:
  with pytest.raises(ValueError):review(conn,ISSUER,[dict(common,subject='one'),dict(common,subject='two')])
  with pytest.raises(ValueError):review(conn,ISSUER,[dict(common,subject='new',role='admin')])
  with pytest.raises(ValueError):review(conn,ISSUER,[{'subject':'one','user_id':str(users['customer'].id),'reviewed_by':'operator','review_reference':'review'},
   {'subject':'two','user_id':str(users['customer'].id),'reviewed_by':'operator','review_reference':'review'}])


def test_live_p4_global_rate_limit(tokens,headers):
 headers('customer')
 # JWT rejection precedes the rate plugin. Exercise the limiter with public and
 # valid authenticated routes, then recover the window before later TLS checks.
 with http_client('https://kong:8443') as c:
  remaining_seconds=60-time.time()%60
  if remaining_seconds<15:time.sleep(remaining_seconds+.1)
  r=c.get('/health');assert r.status_code==200
  assert r.headers['x-ratelimit-limit-minute']=='60'
  try:
   for _ in range(int(r.headers['x-ratelimit-remaining-minute'])):assert c.get('/health').status_code==200
   assert c.get('/api/v1/products/').status_code==429
   assert c.get('/api/v1/auth/me',headers={'Authorization':'Bearer '+tokens['customer']['access_token']}).status_code==429
  finally:time.sleep(60-time.time()%60+1)
  assert c.get('/health').status_code==200
