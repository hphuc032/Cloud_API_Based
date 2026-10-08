"""Disposable user/config marker; no committed password or realm users."""
import json
from pathlib import Path
import secrets
import sys
import httpx
c=httpx.Client(verify='/identity-trust/identity-ca.pem',timeout=30)
base='https://keycloak:8443'
r=c.post(base+'/realms/master/protocol/openid-connect/token',data={'client_id':'admin-cli','grant_type':'password','username':'admin','password':Path('/run/secrets/keycloak_admin_password').read_text().strip()})
r.raise_for_status();headers={'Authorization':'Bearer '+r.json()['access_token']}
realm=base+'/admin/realms/florasecure'
path=Path('/results/persistence-marker.json')
if sys.argv[1]=='prepare':
 name='p3-persist-'+secrets.token_hex(12)
 r=c.post(realm+'/users',headers=headers,json={'username':name,'enabled':True});assert r.status_code==201
 marker={'id':r.headers['location'].rsplit('/',1)[1],'username':name}
 config=c.get(realm,headers=headers).json();marker['displayName']=config.get('displayName')
 config['displayName']=name;assert c.put(realm,headers=headers,json=config).status_code==204
 marker['jwks']=c.get('https://identity-edge:8443/realms/florasecure/protocol/openid-connect/certs').json()
 marker['clients']=c.get(realm+'/clients',headers=headers,params={'clientId':'florasecure-spa'}).json()
 path.write_text(json.dumps(marker));print('prepared')
else:
 marker=json.loads(path.read_text());r=c.get(realm+'/users/'+marker['id'],headers=headers);assert r.status_code==200
 assert r.json()['username']==marker['username']
 config=c.get(realm,headers=headers).json();assert config['displayName']==marker['username']
 assert c.get('https://identity-edge:8443/realms/florasecure/protocol/openid-connect/certs').json()==marker['jwks']
 assert c.get(realm+'/clients',headers=headers,params={'clientId':'florasecure-spa'}).json()==marker['clients']
 issuer='https://identity-edge:8443/realms/florasecure'
 assert c.get(issuer+'/.well-known/openid-configuration').json()['issuer']==issuer
 config['displayName']=marker['displayName'];assert c.put(realm,headers=headers,json=config).status_code==204
 assert c.delete(realm+'/users/'+marker['id'],headers=headers).status_code==204
 print('persisted: user subject, realm edit, SPA configuration, HTTPS discovery')
