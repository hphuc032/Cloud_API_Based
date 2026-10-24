"""Disposable real signing-provider changes; secrets stay under /test-fixtures."""
import json,os,sys,time
from pathlib import Path
import httpx
from jose import jwt
from test_identity import authorize,exchange
from transport import http_client
ISSUER=os.environ['OIDC_ISSUER'];path=Path('/test-fixtures/rotation.json')
data=json.loads(Path('/test-fixtures/identities.json').read_text());user=data['users']['customer']

def issue(c):
 code,verifier,_=authorize(c,user['username'],user['password']);r=exchange(c,code,verifier);assert r.status_code==200
 return r.json()['access_token']

with httpx.Client(verify='/identity-trust/identity-ca.pem',timeout=20,follow_redirects=False) as c:
 r=c.post('https://keycloak:8443/realms/master/protocol/openid-connect/token',data={'client_id':'admin-cli','grant_type':'password','username':'admin','password':Path('/run/secrets/keycloak_admin_password').read_text().strip()});assert r.status_code==200
 h={'Authorization':'Bearer '+r.json()['access_token']};base='https://keycloak:8443/admin/realms/florasecure'
 mode=sys.argv[1]
 if mode=='stage':
  old=issue(c)
  r=c.post(base+'/components',headers=h,json={'name':'disposable-p4-next','providerId':'rsa-generated','providerType':'org.keycloak.keys.KeyProvider','config':{'priority':['2000'],'enabled':['true'],'active':['false'],'algorithm':['RS256'],'keySize':['2048']}});assert r.status_code==201
  provider=r.headers['location'].rsplit('/',1)[1]
  keys=c.get(base+'/keys',headers=h).json()['keys'];newkid=next(k['kid'] for k in keys if k['providerId']==provider)
  public=c.get(ISSUER+'/protocol/openid-connect/certs').json()['keys'];assert newkid in [k['kid'] for k in public]
  path.write_text(json.dumps({'provider':provider,'old_provider':data['provider_id'],'old':old,'newkid':newkid,'oldkid':jwt.get_unverified_header(old)['kid']}))
 elif mode=='activate':
  state=json.loads(path.read_text());r=c.get(base+'/components/'+state['provider'],headers=h);assert r.status_code==200
  component=r.json();component['config']['active']=['true'];assert c.put(base+'/components/'+state['provider'],headers=h,json=component).status_code==204
  state['new']=issue(c);assert jwt.get_unverified_header(state['new'])['kid']==state['newkid'];path.write_text(json.dumps(state));time.sleep(5.1)
  for url in ('https://kong:8443','https://backend:8443'):
   with http_client(url,backend=url.startswith('https://backend:')) as target:
    for label,token in (('old',state['old']),('new',state['new'])):
     response=target.get('/api/v1/auth/me',headers={'Authorization':'Bearer '+token})
     evidence=Path('/results/rotation-http-status.json')
     observations=json.loads(evidence.read_text()) if evidence.exists() else []
     claims=jwt.get_unverified_claims(token)
     observations.append({'phase':'activate','target':url,'key_generation':label,
                          'status':response.status_code,'wall_clock':time.time(),
                          'token_exp':claims.get('exp'),'token_iat':claims.get('iat'),
                          'date':response.headers.get('date')})
     evidence.write_text(json.dumps(observations,indent=2))
     assert response.status_code==200, url+' '+label+' status '+str(response.status_code)
 elif mode=='retire':
  state=json.loads(path.read_text());assert c.delete(base+'/components/'+state['old_provider'],headers=h).status_code==204
  assert state['oldkid'] not in [k['kid'] for k in c.get(ISSUER+'/protocol/openid-connect/certs').json()['keys']]
 elif mode=='verify-retired':
  state=json.loads(path.read_text())
  for url in ('https://kong:8443','https://backend:8443'):
   with http_client(url,backend=url.startswith('https://backend:')) as target:
    assert target.get('/api/v1/auth/me',headers={'Authorization':'Bearer '+state['old']}).status_code==401
    assert target.get('/api/v1/auth/me',headers={'Authorization':'Bearer '+state['new']}).status_code==200
 print('PASS: real Keycloak rotation '+mode+'; no keys or tokens emitted')
