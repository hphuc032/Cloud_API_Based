"""Operator-reviewed fixtures for the disposable production-SPA lab only."""
import hashlib,hmac,json,os,secrets,time
from pathlib import Path
from uuid import uuid4
import psycopg2
from deployment.common import configure_application,database_url
from deployment.identity_mapping import bind
configure_application()
assert os.environ['P0_ISOLATED']=='1' and os.environ['APP_ENV']=='test' and os.environ['APP_DB_NAME']=='p0_baseline'
from app.auth.security import hash_password
path=Path('/test-fixtures/identities.json');data=json.loads(path.read_text())
with psycopg2.connect(database_url('postgres',Path('/run/secrets/postgres_password').read_text().strip())) as conn:
 ids={}
 for role in ['customer_b','staff']:
  user=data['users'][role];uid=str(uuid4());ids[role]=uid
  with conn.cursor() as cur:
   cur.execute('INSERT INTO users(id,email,username,hashed_password,role,is_active) VALUES (%s,%s,%s,%s,%s,true)',
    (uid,user['username']+'@example.com',user['username'],hash_password(secrets.token_urlsafe(40)),'customer' if role=='customer_b' else role))
  bind(conn,trusted_issuer=os.environ['OIDC_ISSUER'],issuer=os.environ['OIDC_ISSUER'],subject=user['subject'],user_id=uid,
       reviewed_by='disposable-operator',review_reference='P5-browser-lab-fixture')
 order=str(uuid4())
 with conn.cursor() as cur:cur.execute('INSERT INTO orders(id,user_id,order_number,total_amount) VALUES (%s,%s,%s,0)',(order,ids['customer_b'],'P5-LAB-'+uuid4().hex))
from app.config import settings
body=' \n'+json.dumps({'event':'payment.success','event_id':'p5-browser-'+uuid4().hex,'order_id':'disposable-ack-only'},indent=2)+'\n '
timestamp=str(int(time.time()))
signature='sha256='+hmac.new(settings.WEBHOOK_SECRET.encode(),timestamp.encode()+b'.'+body.encode(),hashlib.sha256).hexdigest()
data['lab']={'other_order':order,'body':body,'timestamp':timestamp,'signature':signature}
path.write_text(json.dumps(data));print('Disposable lab identities, ownership fixture and short-lived signed delivery prepared; no keys or credentials printed')
