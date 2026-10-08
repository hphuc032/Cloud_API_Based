"""Real Keycloak, verified HTTPS and isolated application PostgreSQL. No auth overrides."""
import base64
import hashlib
import html
import json
import os
from pathlib import Path
import re
import secrets
from urllib.parse import parse_qs, urlparse
from uuid import uuid4

import httpx
from jose import jwt, jwk
import psycopg2
import pytest
from deployment.identity_mapping import bind

ISSUER = os.environ['IDENTITY_ISSUER']
CA = '/identity-trust/identity-ca.pem'
REDIRECT = 'https://localhost:5173/oidc/callback'
CLIENT = 'florasecure-spa'

@pytest.fixture(scope='module')
def identity():
    with httpx.Client(verify=CA, timeout=20, follow_redirects=False) as c:
        yield c

@pytest.fixture(scope='module')
def admin(identity):
    response = identity.post('https://keycloak:8443/realms/master/protocol/openid-connect/token',
        data={'grant_type':'password','client_id':'admin-cli','username':'admin',
              'password':Path('/run/secrets/keycloak_admin_password').read_text().strip()})
    assert response.status_code == 200, 'Disposable bootstrap administrator login failed'
    return {'Authorization':'Bearer '+response.json()['access_token']}

@pytest.fixture
def oidc_user(identity, admin):
    username='p3-'+uuid4().hex
    password=secrets.token_urlsafe(24)+'9!'
    response=identity.post('https://keycloak:8443/admin/realms/florasecure/users',headers=admin,
        json={'username':username,'enabled':True,'emailVerified':True,'email':username+'@example.com',
              'firstName':'P3','lastName':'Disposable','credentials':[{'type':'password','value':password,'temporary':False}]})
    assert response.status_code==201
    user_id=response.headers['location'].rsplit('/',1)[1]
    try:
        yield username,password,user_id
    finally:
        assert identity.delete('https://keycloak:8443/admin/realms/florasecure/users/'+user_id,headers=admin).status_code==204


def discovery(identity):
    response=identity.get(ISSUER+'/.well-known/openid-configuration')
    assert response.status_code==200
    return response.json()


def authorize(identity, username, password, *, challenge=None, method='S256', nonce=None):
    identity.cookies.clear()  # A new disposable browser transaction, no earlier SSO session.
    verifier=secrets.token_urlsafe(48)
    challenge=challenge or base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b'=').decode()
    state=secrets.token_urlsafe(24);nonce=nonce or secrets.token_urlsafe(24)
    response=identity.get(discovery(identity)['authorization_endpoint'],params={
        'client_id':CLIENT,'response_type':'code','scope':'openid profile email','redirect_uri':REDIRECT,
        'state':state,'nonce':nonce,'code_challenge':challenge,'code_challenge_method':method})
    assert response.status_code==200, 'Authorization login page unavailable'
    action=html.unescape(re.search(r'<form[^>]*action="([^"]+)"',response.text).group(1))
    response=identity.post(action,data={'username':username,'password':password,'credentialId':''})
    assert response.status_code==302, 'Disposable user login did not produce an authorization code'
    callback=response.headers['location'];url=urlparse(callback)
    assert url.scheme+'://'+url.netloc+url.path==REDIRECT
    query=parse_qs(url.query)
    assert query['state']==[state] and 'error' not in query
    return query['code'][0],verifier,nonce


def exchange(identity,code,verifier):
    return identity.post(discovery(identity)['token_endpoint'],data={
        'grant_type':'authorization_code','client_id':CLIENT,'redirect_uri':REDIRECT,
        'code':code,'code_verifier':verifier})


def test_discovery_jwks_verified_https(identity):
    config=discovery(identity)
    assert config['issuer']==ISSUER
    assert config['authorization_endpoint'].startswith(ISSUER+'/')
    assert config['token_endpoint'].startswith(ISSUER+'/')
    assert 'S256' in config['code_challenge_methods_supported']
    response=identity.get(config['jwks_uri']);assert response.status_code==200
    keys=response.json()['keys'];signing=[k for k in keys if k.get('use')=='sig' and k.get('alg')=='RS256']
    assert signing
    for key in signing:
        assert key['kty']=='RSA' and key['kid'] and key['n'] and key['e']
        assert not any(field in key for field in ('d','p','q','dp','dq','qi'))
        jwk.construct(key,algorithm='RS256')
    Path('/results/oidc-evidence.json').write_text(json.dumps({'discovery':config,'public_jwks':keys},indent=2))


def test_realm_and_client_reproducible(identity,admin):
    source=json.loads(Path('/realm.json').read_text())
    realm=identity.get('https://keycloak:8443/admin/realms/florasecure',headers=admin).json()
    for field in ('sslRequired','registrationAllowed','resetPasswordAllowed','loginWithEmailAllowed',
                  'duplicateEmailsAllowed','bruteForceProtected','accessTokenLifespan','ssoSessionIdleTimeout',
                  'ssoSessionMaxLifespan','revokeRefreshToken','refreshTokenMaxReuse','defaultSignatureAlgorithm'):
        assert realm[field]==source[field],field
    clients=identity.get('https://keycloak:8443/admin/realms/florasecure/clients',headers=admin,params={'clientId':CLIENT}).json()
    assert len(clients)==1
    target=clients[0];expected=source['clients'][0]
    for field in ('publicClient','standardFlowEnabled','implicitFlowEnabled','directAccessGrantsEnabled',
                  'serviceAccountsEnabled','redirectUris','webOrigins'):
        assert target[field]==expected[field],field
    scopes=identity.get('https://keycloak:8443/admin/realms/florasecure/clients/'+target['id']+'/default-client-scopes',headers=admin).json()
    assert {scope['name'] for scope in scopes}==set(expected['defaultClientScopes'])
    assert target['attributes']['pkce.code.challenge.method']=='S256'
    assert '*' not in ''.join(target['redirectUris']+target['webOrigins'])
    mappers=identity.get('https://keycloak:8443/admin/realms/florasecure/clients/'+target['id']+'/protocol-mappers/models',headers=admin).json()
    assert any(m['config'].get('included.custom.audience')=='florasecure-api' for m in mappers)


def test_code_pkce_tokens_audience_nonce_and_rotation(identity,oidc_user,users):
    username,password,sub=oidc_user
    code,verifier,nonce=authorize(identity,username,password)
    response=exchange(identity,code,verifier);assert response.status_code==200
    tokens=response.json();keys=identity.get(discovery(identity)['jwks_uri']).json()
    access=jwt.decode(tokens['access_token'],keys,algorithms=['RS256'],issuer=ISSUER,audience='florasecure-api')
    id_token=jwt.decode(tokens['id_token'],keys,algorithms=['RS256'],issuer=ISSUER,audience=CLIENT,access_token=tokens['access_token'])
    assert access['sub']==id_token['sub']==sub
    with psycopg2.connect(os.environ['P0_ADMIN_DATABASE_URL']) as conn:
        bind(conn,trusted_issuer=ISSUER,issuer=access['iss'],subject=access['sub'],
             user_id=users['customer'].id,reviewed_by='disposable-operator',review_reference='P3-live-sub-review')
        with conn.cursor() as cur:
            cur.execute('SELECT user_id FROM external_identities WHERE issuer=%s AND subject=%s',(ISSUER,sub))
            assert str(cur.fetchone()[0])==str(users['customer'].id)
    assert id_token['nonce']==nonce
    # P3 must not activate the future issuer or change existing application authentication.
    from transport import http_client
    with http_client('https://kong:8443') as application:
        response=application.get('/api/v1/auth/me',headers={'Authorization':'Bearer '+tokens['access_token']})
        assert response.status_code==401
    assert 0 < access['exp']-access['iat'] <= 300
    Path('/results/token-verification-evidence.json').write_text(json.dumps({
        'issuer':access['iss'],'access_audience':access['aud'],'id_audience':id_token['aud'],
        'algorithm':jwt.get_unverified_header(tokens['access_token'])['alg'],
        'access_lifetime_seconds':access['exp']-access['iat'],
        'signature_verified':True,'nonce_matches':True,'at_hash_verified':True,
        'subject_matches_created_identity':True,'keycloak_token_rejected_by_current_app':True,
    },indent=2))
    # Check normal refresh before replaying credentials, which can revoke the client session.
    rotated=identity.post(discovery(identity)['token_endpoint'],data={'grant_type':'refresh_token','client_id':CLIENT,'refresh_token':tokens['refresh_token']})
    assert rotated.status_code==200, {"status":rotated.status_code,"error":rotated.json().get("error"),"description":rotated.json().get("error_description")}
    assert identity.post(discovery(identity)['token_endpoint'],data={'grant_type':'refresh_token','client_id':CLIENT,'refresh_token':tokens['refresh_token']}).status_code==400
    assert exchange(identity,code,verifier).status_code==400


def test_wrong_pkce_verifier_rejected(identity,oidc_user):
    username,password,_=oidc_user
    code,_,_=authorize(identity,username,password)
    response=exchange(identity,code,secrets.token_urlsafe(48))
    assert response.status_code==400 and response.json()['error']=='invalid_grant'


@pytest.mark.parametrize('redirect',[REDIRECT+'/extra','https://evil.example/callback','http://localhost:5173/oidc/callback'])
def test_invalid_redirect_not_followed(identity,redirect):
    response=identity.get(discovery(identity)['authorization_endpoint'],params={'client_id':CLIENT,'response_type':'code','scope':'openid','redirect_uri':redirect})
    assert response.status_code==400 and 'location' not in response.headers


@pytest.mark.parametrize('challenge', [{}, {'code_challenge':'plain-verifier','code_challenge_method':'plain'}])
def test_pkce_s256_required(identity,challenge):
    response=identity.get(discovery(identity)['authorization_endpoint'],params={'client_id':CLIENT,'response_type':'code','scope':'openid','redirect_uri':REDIRECT,**challenge})
    assert response.status_code in (302,400)
    assert response.status_code==400 or 'error=invalid_request' in response.headers['location']


def test_password_grant_disabled(identity,oidc_user):
    username,password,_=oidc_user
    response=identity.post(discovery(identity)['token_endpoint'],data={'grant_type':'password','client_id':CLIENT,'username':username,'password':password})
    assert response.status_code==400 and response.json()['error']=='unauthorized_client'


@pytest.mark.parametrize('response_type',['token','id_token','code token'])
def test_implicit_and_hybrid_disabled(identity,response_type):
    response=identity.get(discovery(identity)['authorization_endpoint'],params={'client_id':CLIENT,'response_type':response_type,'redirect_uri':REDIRECT,'scope':'openid','nonce':'test-nonce','state':'test-state',
        'code_challenge':base64.urlsafe_b64encode(hashlib.sha256(secrets.token_urlsafe(48).encode()).digest()).rstrip(b'=').decode(),'code_challenge_method':'S256'})
    assert response.status_code in (302,400)
    if response.status_code==302:
        assert 'error=' in response.headers['location'] and 'access_token=' not in response.headers['location']


def test_public_edge_denies_admin_and_master(identity):
    for path in ('/admin/','/realms/master/.well-known/openid-configuration','/health/ready','/metrics'):
        assert identity.get('https://identity-edge:8443'+path).status_code==404


def mapping(conn,users,**changes):
    args={'trusted_issuer':ISSUER,'issuer':ISSUER,'subject':'reviewed-subject','user_id':users['customer'].id,
          'reviewed_by':'disposable-operator','review_reference':'P3-test-review'}
    args.update(changes);bind(conn,**args)


def test_mapping_preserves_ids_orders_and_roles(users,orders):
    with psycopg2.connect(os.environ['P0_ADMIN_DATABASE_URL']) as conn:
        mapping(conn,users)
        with conn.cursor() as cur:
            cur.execute('SELECT e.user_id,u.role,u.is_active,o.id FROM external_identities e JOIN users u ON u.id=e.user_id JOIN orders o ON o.user_id=u.id')
            user_id,role,active,order_id=cur.fetchone()
            assert str(user_id)==str(users['customer'].id) and str(order_id)==orders['customer']
            assert role=='customer' and active
            cur.execute("SELECT column_name,data_type,is_nullable FROM information_schema.columns WHERE table_name='external_identities' ORDER BY ordinal_position")
            columns=cur.fetchall()
            cur.execute("SELECT conname,pg_get_constraintdef(oid) FROM pg_constraint WHERE conrelid='external_identities'::regclass ORDER BY conname")
            Path('/results/identity-schema.json').write_text(json.dumps({'columns':columns,'constraints':cur.fetchall()},indent=2))


@pytest.mark.parametrize('changes',[{}, {'user_id':'other'}, {'subject':'conflicting-subject'}])
def test_duplicate_or_conflicting_mappings_rejected(users,changes):
    if changes.get('user_id')=='other':changes={'user_id':users['customer_b'].id}
    with psycopg2.connect(os.environ['P0_ADMIN_DATABASE_URL']) as conn:
        mapping(conn,users)
    with pytest.raises(psycopg2.IntegrityError):
        with psycopg2.connect(os.environ['P0_ADMIN_DATABASE_URL']) as conn:
            mapping(conn,users,**changes)


def test_unknown_user_and_untrusted_issuer_rejected(users):
    with pytest.raises(psycopg2.IntegrityError):
        with psycopg2.connect(os.environ['P0_ADMIN_DATABASE_URL']) as conn:
            mapping(conn,users,user_id=uuid4())
    with psycopg2.connect(os.environ['P0_ADMIN_DATABASE_URL']) as conn:
        with pytest.raises(ValueError):mapping(conn,users,issuer='https://evil.example/realms/florasecure')


def test_email_collision_never_links_or_creates_mapping(identity,admin,users,oidc_user):
    # Give an unrelated Keycloak user the application's existing customer email.
    _,_,sub=oidc_user
    response=identity.put('https://keycloak:8443/admin/realms/florasecure/users/'+sub,headers=admin,json={'email':users['customer'].email})
    assert response.status_code==204
    with psycopg2.connect(os.environ['P0_ADMIN_DATABASE_URL']) as conn,conn.cursor() as cur:
        cur.execute('SELECT count(*) FROM external_identities');assert cur.fetchone()[0]==0
        cur.execute('SELECT id,role FROM users WHERE email=%s',(users['customer'].email,))
        value=cur.fetchone();assert str(value[0])==str(users['customer'].id) and value[1]=='customer'


def test_runtime_cannot_create_identity_links():
    with pytest.raises(psycopg2.errors.InsufficientPrivilege):
        with psycopg2.connect(os.environ['DATABASE_URL']) as conn,conn.cursor() as cur:
            cur.execute('SELECT * FROM external_identities')


from test_database import isolated_database, alembic


def test_additive_migration_and_rollback_preserve_application_data(isolated_database):
    _,url=isolated_database
    alembic(url,'upgrade','0001_initial_schema')
    uid,pid,oid,iid=[str(uuid4()) for _ in range(4)]
    with psycopg2.connect(url) as conn,conn.cursor() as cur:
        cur.execute("INSERT INTO users(id,email,username,hashed_password,role) VALUES (%s,'p3@example.com','p3','synthetic','customer')",(uid,))
        cur.execute("INSERT INTO products(id,sku,name,price,created_by) VALUES (%s,'p3','P3',10,%s)",(pid,uid))
        cur.execute("INSERT INTO orders(id,user_id,order_number,total_amount) VALUES (%s,%s,'p3',10)",(oid,uid))
        cur.execute("INSERT INTO order_items(id,order_id,product_id,quantity,unit_price) VALUES (%s,%s,%s,1,10)",(iid,oid,pid))
    def snapshot():
        with psycopg2.connect(url) as conn,conn.cursor() as cur:
            result={}
            for table in ('users','products','orders','order_items'):
                cur.execute('SELECT row_to_json(t)::text FROM '+table+' t ORDER BY id')
                result[table]=cur.fetchall()
            return result
    before=snapshot()
    alembic(url,'upgrade','head');alembic(url,'upgrade','head')
    assert snapshot()==before
    with psycopg2.connect(url) as conn,conn.cursor() as cur:
        bind(conn,trusted_issuer=ISSUER,issuer=ISSUER,subject='keycloak-sub',user_id=uid,reviewed_by='operator',review_reference='review')
        cur.execute("SELECT confdeltype FROM pg_constraint WHERE conrelid='external_identities'::regclass AND contype='f'")
        assert cur.fetchone()[0]=='r'
    with pytest.raises(psycopg2.errors.ForeignKeyViolation):
        with psycopg2.connect(url) as conn,conn.cursor() as cur:
            cur.execute('DELETE FROM users WHERE id=%s',(uid,))
    alembic(url,'downgrade','0001_initial_schema')
    assert snapshot()==before
    with psycopg2.connect(url) as conn,conn.cursor() as cur:
        cur.execute("SELECT to_regclass('external_identities')");assert cur.fetchone()[0] is None
    alembic(url,'upgrade','head');assert snapshot()==before
