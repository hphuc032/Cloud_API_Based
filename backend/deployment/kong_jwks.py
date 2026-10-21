"""Generate a complete DB-less Kong release from verified public Keycloak keys.
Publish only after success. Operators must parse then reload Kong; admin API stays off.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
from urllib.parse import urlsplit
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from jose.utils import base64url_decode
from deployment.jwks import fetch_signing_keys


def render(issuer, ca, origins):
    parsed = urlsplit(issuer)
    if (parsed.scheme != 'https' or not parsed.hostname or parsed.username or parsed.password or
            parsed.query or parsed.fragment or not parsed.path.startswith('/realms/') or issuer.endswith('/')):
        raise ValueError('An exact HTTPS realm issuer is required')
    if not isinstance(origins,list) or not origins or any(not isinstance(o,str) or
            urlsplit(o).scheme != 'https' or not urlsplit(o).hostname or urlsplit(o).username or
            urlsplit(o).password or urlsplit(o).query or urlsplit(o).fragment or
            urlsplit(o).path not in ('','/') or '*' in o for o in origins):
        raise ValueError('Exact HTTPS browser origins required')
    keys = fetch_signing_keys(issuer, ca)
    credentials = []
    for kid,key in sorted(keys.items()):
        public = rsa.RSAPublicNumbers(int.from_bytes(base64url_decode(key['e'].encode()),'big'),
                                     int.from_bytes(base64url_decode(key['n'].encode()),'big')).public_key()
        credentials.append({'key':kid,'algorithm':'RS256','rsa_public_key':public.public_bytes(
            serialization.Encoding.PEM,serialization.PublicFormat.SubjectPublicKeyInfo).decode()})
    routes = [
        {'name':'public-products','paths':[r'~/api/v1/products(?:/[^/]+)?/?$'],'methods':['GET','HEAD'],'regex_priority':20},
        {'name':'public-health','paths':[r'~/health(?:/ready)?$'],'methods':['GET','HEAD'],'regex_priority':20},
        {'name':'hmac-webhook','paths':[r'~/api/v1/webhooks/receive$'],'methods':['POST'],'regex_priority':20},
        {'name':'disabled-debug-helper','paths':[r'~/api/v1/webhooks/test-signature$'],'regex_priority':30,
         'plugins':[{'name':'request-termination','config':{'status_code':404,'message':'Not found'}}]},
        {'name':'retired-auth','paths':[r'~/api/v1/auth/(?:login|register|refresh|logout)$'],'regex_priority':30,
         'plugins':[{'name':'request-termination','config':{'status_code':410,'message':'Use the identity provider'}}]},
        {'name':'protected-api','paths':['/api/v1'],'plugins':[{'name':'jwt','config':{
            'key_claim_name':'kid','header_names':['authorization'],'uri_param_names':[], 'cookie_names':[],
            # Keycloak omits optional nbf; Kong requires every configured claim.
            # FastAPI independently enforces nbf when present.
            'claims_to_verify':['exp'],'maximum_expiration':300,'run_on_preflight':False}}]},
    ]
    for route in routes:
        route.update(strip_path=False,preserve_host=False,protocols=['https'])
    return {'_format_version':'3.0','_transform':True,
        'services':[{'name':'fastapi-service','url':'https://backend:8443','tls_verify':True,'tls_verify_depth':2,'routes':routes}],
        'consumers':[{'username':'trusted-keycloak-signing-keys','jwt_secrets':credentials}],
        # JWT credentials share a signing-key consumer, not a user. Preserve the
        # legacy gateway's effective per-IP policy instead of collapsing all users.
        'plugins':[{'name':'rate-limiting','config':{'minute':60,'policy':'local','limit_by':'ip'}},
                   {'name':'cors','config':{'origins':origins,'methods':['GET','HEAD','POST','PUT','PATCH','DELETE','OPTIONS'],
                    'headers':['Authorization','Content-Type','X-Webhook-Signature'], 'credentials':False,'max_age':300}}]}


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',required=True)
    actions=p.add_mutually_exclusive_group();actions.add_argument('--candidate',action='store_true')
    actions.add_argument('--promote-digest');actions.add_argument('--rollback',action='store_true');args=p.parse_args()
    target=Path(args.output);target.parent.mkdir(parents=True,exist_ok=True)
    candidate=target.with_name('kong.candidate.json');previous=target.with_name('kong.previous.json')
    if args.promote_digest:
        raw=candidate.read_bytes()
        if len(raw)>524288 or hashlib.sha256(raw).hexdigest()!=args.promote_digest:
            raise ValueError('Parsed candidate digest does not match; promotion refused')
        if target.exists():previous.write_bytes(target.read_bytes());previous.chmod(0o644)
    elif args.rollback:raw=previous.read_bytes()
    else:
        document=render(os.environ['OIDC_ISSUER'],os.environ.get('OIDC_CA_FILE'),json.loads(os.environ['OIDC_ORIGINS']))
        policy=os.environ.get('GATEWAY_POLICY','p4')
        if policy=='p5':
            from deployment.p5_gateway import harden
            document=harden(document)
        elif policy=='p6':
            from deployment.p6_gateway import observe
            document=observe(document)
        elif policy!='p4':raise ValueError('Unknown gateway policy')
        raw=(json.dumps(document,indent=2)+'\n').encode()
        if args.candidate:target=candidate
    temporary=target.with_suffix('.pending');temporary.write_bytes(raw)
    temporary.chmod(0o644);temporary.replace(target)
    print(hashlib.sha256(raw).hexdigest())
