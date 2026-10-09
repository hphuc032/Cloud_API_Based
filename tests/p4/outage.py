"""Actual HTTPS outage coordination; bounded cache and independent backend rejection."""
import json,os,time
from pathlib import Path
from jose import JWTError,jwt
from deployment.jwks import JWKSCache
from transport import http_client
directory=Path('/test-fixtures');data=json.loads((directory/'rotation.json').read_text());token=data['new'];kid=data['newkid']
cache=JWKSCache(os.environ['OIDC_ISSUER'],'/identity-trust/identity-ca.pem',ttl=2,refresh_interval=1)
cache.key(kid);attempt=cache.last_attempt
for _ in range(10):
 try:cache.key('unknown-untrusted-kid');raise AssertionError('Unknown key accepted')
 except JWTError:pass
assert cache.last_attempt==attempt
with http_client('https://backend:8443',backend=True) as backend:
 assert backend.get('/api/v1/auth/me',headers={'Authorization':'Bearer '+token}).status_code==200
 (directory/'outage-ready').touch()
 for _ in range(100):
  if (directory/'outage-offline').exists():break
  time.sleep(.1)
 else:raise AssertionError('Outage was not triggered')
 assert cache.key(kid)
 assert backend.get('/api/v1/auth/me',headers={'Authorization':'Bearer '+token}).status_code==200
 time.sleep(3)
 try:cache.key(kid);raise AssertionError('Expired JWKS used during outage')
 except JWTError:pass
 # Actual application default TTL is 60 seconds; cached tokens are never trusted beyond it.
 time.sleep(60)
 assert backend.get('/api/v1/auth/me',headers={'Authorization':'Bearer '+token}).status_code==401
print('PASS: real JWKS outage, warm cache bounded to TTL, unknown-key throttling, expired-cache denial')
