"""Privileged disposable fixture; never run against existing application data."""
import json,os,sys,secrets
from pathlib import Path
from uuid import uuid4
import httpx,psycopg2
from deployment.common import configure_application,database_url
from deployment.identity_mapping import bind
configure_application()
assert os.environ['P0_ISOLATED']=='1' and os.environ['APP_DB_NAME']=='p0_baseline'
data=json.loads(Path('/test-fixtures/identities.json').read_text());user=data['users']['customer']
if sys.argv[1]=='prepare':
 from app.auth.security import hash_password
 with psycopg2.connect(database_url('postgres',Path('/run/secrets/postgres_password').read_text().strip())) as conn:
  uid=str(uuid4())
  with conn.cursor() as cur:
   cur.execute("INSERT INTO users(id,email,username,hashed_password,role,is_active) VALUES (%s,%s,%s,%s,'customer',true)",
    (uid,user['username']+'@example.com',user['username'],hash_password(secrets.token_urlsafe(40))))
  bind(conn,trusted_issuer=os.environ['OIDC_ISSUER'],issuer=os.environ['OIDC_ISSUER'],subject=user['subject'],user_id=uid,reviewed_by='disposable-test',review_reference='P4-browser')
 data['application_id']=uid;Path('/test-fixtures/identities.json').write_text(json.dumps(data));print('Disposable browser account explicitly mapped')
elif sys.argv[1]=='expire':
 with httpx.Client(verify='/identity-trust/identity-ca.pem',timeout=20) as c:
  r=c.post('https://keycloak:8443/realms/master/protocol/openid-connect/token',data={'client_id':'admin-cli','grant_type':'password','username':'admin','password':Path('/run/secrets/keycloak_admin_password').read_text().strip()});assert r.status_code==200
  r=c.post('https://keycloak:8443/admin/realms/florasecure/users/'+user['subject']+'/logout',headers={'Authorization':'Bearer '+r.json()['access_token']});assert r.status_code==204
 print('Disposable identity sessions expired at the IdP')
