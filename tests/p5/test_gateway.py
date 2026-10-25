"""Live Kong behavior; no simulated plugin results or disabled authentication."""
import json,time
from pathlib import Path
import httpx,pytest
from test_cutover import headers,tokens,identity,admin,oidc_user
from test_hardening import signed,raw,envelope
from transport import http_client,wait_for_rate_limit_window

HEADERS={'strict-transport-security':'max-age=31536000','x-content-type-options':'nosniff','x-frame-options':'DENY','x-xss-protection':'0'}

def check_headers(response):
 for k,v in HEADERS.items():assert response.headers[k]==v
 assert "default-src 'none'" in response.headers['content-security-policy']
 assert 'camera=()' in response.headers['permissions-policy']


def test_success_and_gateway_error_headers():
 with http_client('https://kong:8443') as c:
  for path,status in [('/health',200),('/api/v1/auth/me',401),('/api/v1/webhooks/test-signature',404),('/api/v1/auth/login',410),('/no-route',404)]:
   r=c.get(path);assert r.status_code==status;check_headers(r)
  body=b'x'*65537
  r=c.post('/api/v1/webhooks/receive',content=body,headers=signed(body));assert r.status_code==413;check_headers(r)


def test_exact_cors_and_hmac_preflight():
 with http_client('https://kong:8443') as c:
  for origin,allowed in [('https://localhost:5174',True),('https://localhost:5174.evil.test',False),('http://localhost:5174',False)]:
   r=c.options('/api/v1/webhooks/receive',headers={'Origin':origin,'Access-Control-Request-Method':'POST','Access-Control-Request-Headers':'X-Signature,X-Timestamp,Content-Type'})
   assert r.status_code in (200,204)
   assert (r.headers.get('access-control-allow-origin')==origin)==allowed
   if allowed:
    assert {'x-signature','x-timestamp'}<=set(x.strip().lower() for x in r.headers['access-control-allow-headers'].split(','))


def test_live_webhook_public_retry_and_forgery():
 with http_client('https://kong:8443') as c:
  body=raw(envelope());h=signed(body)
  a=c.post('/api/v1/webhooks/receive',content=body,headers=h);b=c.post('/api/v1/webhooks/receive',content=body,headers=h)
  assert a.status_code==b.status_code==200 and a.json()==b.json()
  assert b.headers['x-webhook-replayed']=='true'
  h['X-Signature']='sha256='+'0'*64
  assert c.post('/api/v1/webhooks/receive',content=body,headers=h).status_code==403


def test_keycloak_own_bruteforce_configuration(identity,admin):
 actual=identity.get('https://keycloak:8443/admin/realms/florasecure',headers=admin)
 assert actual.status_code==200
 expected=json.loads(Path('/realm-p5.json').read_text())
 for field in ['bruteForceProtected','failureFactor','waitIncrementSeconds','maxFailureWaitSeconds','minimumQuickLoginWaitSeconds','quickLoginCheckMilliSeconds']:
  assert actual.json()[field]==expected[field]


def test_pre_auth_throttle_rejects_forwarding_header_spoofing():
 # Begin a clean fixed window; no production counters or policy are reset.
 evidence=[]
 wait_for_rate_limit_window(evidence)
 with http_client('https://kong:8443') as c:
  def record(r,expected):
   row={'status':r.status_code,'expected':expected,'time':time.time(),
    'headers':{k:v for k,v in r.headers.items() if k.lower() in
     ('date','retry-after','ratelimit-limit','ratelimit-remaining','ratelimit-reset','x-ratelimit-layer')}}
   evidence.append(row)
   Path('/results/p5-preauth-burst.json').write_text(json.dumps(evidence,indent=2))
   return row
  for i in range(60):
   r=c.get('/api/v1/users/',headers={'X-Forwarded-For':f'198.51.100.{i+1}','X-Real-IP':f'203.0.113.{i+1}'})
   observed=record(r,401)
   assert r.status_code==401,observed
  r=c.get('/api/v1/users/',headers={'X-Forwarded-For':'192.0.2.99','X-Real-IP':'192.0.2.99'})
  observed=record(r,429)
  assert r.status_code==429 and r.headers['x-ratelimit-layer']=='pre-auth',observed
  assert int(r.headers['retry-after'])>0;check_headers(r)
 # Avoid carrying intentional rejection traffic into later business regressions.
 wait_for_rate_limit_window(evidence)
 Path('/results/p5-preauth-burst.json').write_text(json.dumps(evidence,indent=2))


def test_keycloak_repeated_wrong_password_is_temporarily_disabled(identity,admin,oidc_user):
 import base64,hashlib,html,re,secrets
 username,_,user_id=oidc_user
 for _ in range(6):
  identity.cookies.clear();verifier=secrets.token_urlsafe(48)
  challenge=base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b'=').decode()
  r=identity.get('https://identity-edge:8443/realms/florasecure/protocol/openid-connect/auth',params={
   'client_id':'florasecure-spa','response_type':'code','scope':'openid','redirect_uri':'https://localhost:5174/oidc/callback',
   'state':secrets.token_urlsafe(16),'nonce':secrets.token_urlsafe(16),'code_challenge':challenge,'code_challenge_method':'S256'})
  assert r.status_code==200
  action=html.unescape(re.search(r'<form[^>]*action="([^"]+)"',r.text).group(1))
  r=identity.post(action,data={'username':username,'password':secrets.token_urlsafe(32),'credentialId':''})
  assert r.status_code==200 and 'code=' not in r.headers.get('location','')
  time.sleep(.1)  # allow the asynchronous brute-force worker to record failures
 for _ in range(20):
  r=identity.get('https://keycloak:8443/admin/realms/florasecure/attack-detection/brute-force/users/'+user_id,headers=admin)
  assert r.status_code==200
  if r.json().get('disabled'):break
  time.sleep(.2)
 assert r.json().get('disabled') is True
