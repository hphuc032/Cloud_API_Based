"""Public-state fingerprints for the disposable identity database upgrade drill."""
import hashlib
import json
import os
from pathlib import Path
import sys

import httpx
import psycopg2
from psycopg2 import sql
from deployment.common import configure_application, database_url

configure_application()
assert os.environ.get('P0_ISOLATED')=='1' and os.environ['APP_DB_NAME']=='p0_baseline'
path=Path('/results/identity-upgrade-state.json')
phase=sys.argv[1]
issuer=os.environ['OIDC_ISSUER']
base='https://keycloak:8443'
with httpx.Client(verify='/identity-trust/identity-ca.pem',timeout=30,trust_env=False) as c:
    token=c.post(base+'/realms/master/protocol/openid-connect/token',data={
        'client_id':'admin-cli','grant_type':'password','username':'admin',
        'password':Path('/run/secrets/keycloak_admin_password').read_text().strip()})
    assert token.status_code==200,'Disposable admin authentication failed'
    h={'Authorization':'Bearer '+token.json()['access_token']}
    realm_url=base+'/admin/realms/florasecure'
    if phase=='prepare':
        marker='upgrade-marker-'+os.environ['HOSTNAME']
        assert c.put(realm_url,headers=h,json={'displayName':marker}).status_code==204
    realm=c.get(realm_url,headers=h).json()
    clients=c.get(realm_url+'/clients',headers=h,params={'clientId':'florasecure-spa'}).json()
    assert len(clients)==1
    client=clients[0]
    public_keys=c.get(issuer+'/protocol/openid-connect/certs').json()['keys']
    rsa_keys=sorted([{k:j.get(k) for k in ['kty','kid','n','e','alg','use']} for j in public_keys
                     if j.get('kty')=='RSA'],key=lambda j:j['kid'])
    users=c.get(realm_url+'/users',headers=h,params={'max':1000}).json()
    users=sorted([{k:u.get(k) for k in ['id','username','enabled','emailVerified']} for u in users],key=lambda u:u['id'])
    discovery=c.get(issuer+'/.well-known/openid-configuration').json()
    assert discovery['issuer']==issuer
    snapshot={'issuer':issuer,'realm':{k:realm.get(k) for k in ['id','realm','displayName',
        'registrationAllowed','resetPasswordAllowed','revokeRefreshToken','refreshTokenMaxReuse',
        'accessTokenLifespan','ssoSessionIdleTimeout','ssoSessionMaxLifespan']},
        'client':{k:client.get(k) for k in ['id','clientId','publicClient','standardFlowEnabled',
            'implicitFlowEnabled','directAccessGrantsEnabled','redirectUris','webOrigins']},
        'users':users,'rsa_jwks_sha256':hashlib.sha256(json.dumps(rsa_keys,sort_keys=True).encode()).hexdigest()}

admin=database_url('postgres',Path('/run/secrets/postgres_password').read_text().strip())
snapshot['application_tables']={}
with psycopg2.connect(admin) as conn,conn.cursor() as cur:
    for table in ['users','external_identities','products','orders','order_items','webhook_receipts']:
        cur.execute(sql.SQL('SELECT row_to_json(t)::text FROM {} t ORDER BY row_to_json(t)::text').format(sql.Identifier(table)))
        values=[row[0] for row in cur.fetchall()]
        snapshot['application_tables'][table]={'rows':len(values),
            'sha256':hashlib.sha256('\n'.join(values).encode()).hexdigest()}
    cur.execute('SELECT count(*) FROM external_identities')
    assert cur.fetchone()[0]==4
    cur.execute('SELECT count(*) FROM orders')
    assert cur.fetchone()[0]==2
if phase=='prepare':path.write_text(json.dumps(snapshot,indent=2))
else:assert snapshot==json.loads(path.read_text()),'Identity, policy, signing key or application state changed'
print('PASS: stable issuer/realm/client/user IDs, realm marker, RSA keys and application rows; no credentials exported')
