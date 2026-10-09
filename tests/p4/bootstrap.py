"""Disposable IdP signing provider/accounts. Generated private material stays in temporary mounts."""
import json,os,secrets
from pathlib import Path
from uuid import uuid4
from datetime import datetime,timedelta,timezone
import httpx
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import hashes,serialization
from cryptography import x509
from cryptography.x509.oid import NameOID
from test_identity import authorize,exchange
from jose import jwt

with httpx.Client(verify='/identity-trust/identity-ca.pem',timeout=20,follow_redirects=False) as c:
 token=c.post('https://keycloak:8443/realms/master/protocol/openid-connect/token',data={
  'grant_type':'password','client_id':'admin-cli','username':'admin','password':Path('/run/secrets/keycloak_admin_password').read_text().strip()})
 assert token.status_code==200
 headers={'Authorization':'Bearer '+token.json()['access_token']}
 key=rsa.generate_private_key(public_exponent=65537,key_size=2048)
 name=x509.Name([x509.NameAttribute(NameOID.COMMON_NAME,'Disposable P4 JWT signer')]);now=datetime.now(timezone.utc)
 cert=x509.CertificateBuilder().subject_name(name).issuer_name(name).public_key(key.public_key()).serial_number(x509.random_serial_number()).not_valid_before(now-timedelta(minutes=1)).not_valid_after(now+timedelta(days=1)).sign(key,hashes.SHA256())
 pem=key.private_bytes(serialization.Encoding.PEM,serialization.PrivateFormat.PKCS8,serialization.NoEncryption())
 response=c.post('https://keycloak:8443/admin/realms/florasecure/components',headers=headers,json={
  'name':'disposable-p4-signing-provider','providerId':'rsa','providerType':'org.keycloak.keys.KeyProvider',
  'config':{'privateKey':[pem.decode()],'certificate':[cert.public_bytes(serialization.Encoding.PEM).decode()],
            'priority':['1000'],'enabled':['true'],'active':['true'],'algorithm':['RS256']}})
 assert response.status_code==201,'Disposable RSA provider import failed'
 Path('/test-fixtures/signing.key').write_bytes(pem)
 data={'provider_id':response.headers['location'].rsplit('/',1)[1],'users':{}}
 for role in ('customer','customer_b','staff','admin'):
  username='p4-'+role+'-'+uuid4().hex;password=secrets.token_urlsafe(32)+'9!'
  r=c.post('https://keycloak:8443/admin/realms/florasecure/users',headers=headers,json={
   'username':username,'enabled':True,'emailVerified':True,'firstName':'P4','lastName':'Disposable','email':username+'@example.com',
   'credentials':[{'type':'password','value':password,'temporary':False}]})
  assert r.status_code==201
  code,verifier,nonce=authorize(c,username,password);r=exchange(c,code,verifier);assert r.status_code==200
  data['users'][role]={'username':username,'password':password,'subject':jwt.get_unverified_claims(r.json()['access_token'])['sub'],'tokens':r.json()}
 Path('/test-fixtures/identities.json').write_text(json.dumps(data))
 print('Disposable signer and four test identities prepared; no credentials printed')
