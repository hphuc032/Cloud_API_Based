"""Reviewed migration/provisioning manifest. Dry-run first; exact report digest authorizes apply.
Never consulted by authentication. No email matching; no role claim assignment.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
from uuid import UUID, uuid4
import secrets
import psycopg2
from deployment.identity_mapping import bind


def review(conn, issuer, manifest):
    from urllib.parse import urlsplit
    url=urlsplit(issuer)
    if url.scheme!='https' or not url.hostname or url.username or url.password or url.query or url.fragment or not url.path.startswith('/realms/') or issuer.endswith('/'):
        raise ValueError('Exact trusted HTTPS issuer required')
    if not isinstance(manifest,list) or not 1<=len(manifest)<=1000:
        raise ValueError('A bounded explicit manifest is required')
    report=[];subjects=set();accounts=set();emails=set();usernames=set()
    with conn.cursor() as cur:
        for item in manifest:
            if not isinstance(item,dict) or set(item)-{'subject','user_id','email','username','reviewed_by','review_reference'}:
                raise ValueError('Unsupported manifest fields; role assignment is prohibited')
            sub=item.get('subject')
            if not isinstance(sub,str) or not sub.strip() or len(sub)>255 or any(ord(c)<32 for c in sub) or sub in subjects:
                raise ValueError('Missing or duplicate subject')
            subjects.add(sub)
            if not item.get('reviewed_by','').strip() or not item.get('review_reference','').strip():
                raise ValueError('Operator review evidence required')
            cur.execute('SELECT user_id FROM external_identities WHERE issuer=%s AND subject=%s',(issuer,sub))
            if cur.fetchone():raise ValueError('Subject already bound')
            row=dict(item)
            if item.get('user_id'):
                uid=str(UUID(item['user_id']))
                if uid in accounts:raise ValueError('Duplicate application account')
                accounts.add(uid)
                cur.execute('SELECT role,is_active FROM users WHERE id=%s',(uid,));user=cur.fetchone()
                if not user:raise ValueError('Unknown explicit application ID')
                cur.execute('SELECT 1 FROM external_identities WHERE issuer=%s AND user_id=%s',(issuer,uid))
                if cur.fetchone():raise ValueError('Application account already bound')
                row.update(user_id=uid,current_role=user[0],current_active=user[1],operation='bind-existing')
            else:
                email=item.get('email','');username=item.get('username','')
                if not isinstance(email,str) or not email or len(email)>255 or not isinstance(username,str) or not username or len(username)>100:
                    raise ValueError('Reviewed email/username required for new account')
                if email.casefold() in emails or username.casefold() in usernames:raise ValueError('Duplicate new account in reviewed batch')
                emails.add(email.casefold());usernames.add(username.casefold())
                cur.execute('SELECT 1 FROM users WHERE lower(email)=lower(%s) OR lower(username)=lower(%s)',(email,username))
                if cur.fetchone():raise ValueError('Collision; automatic account linking is forbidden')
                row.update(operation='create-customer',current_role='customer',current_active=True)
            report.append(row)
    body={'trusted_issuer':issuer,'changes':report}
    digest=hashlib.sha256(json.dumps(body,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    return body,digest


def apply(conn,issuer,manifest,approved_digest):
    # Serialize reviewed operators and pin the inspected account state until commit.
    with conn.cursor() as cur:
        cur.execute('LOCK TABLE users, external_identities IN SHARE ROW EXCLUSIVE MODE')
    report,digest=review(conn,issuer,manifest)
    if not secrets.compare_digest(digest,approved_digest):raise ValueError('Review digest changed or not approved')
    for row in report['changes']:
        if row['operation']=='bind-existing':uid=row['user_id']
        else:
            from app.auth.security import hash_password
            uid=str(uuid4())
            # Local rollback login requires an explicit password reset; no known local password.
            with conn.cursor() as cur:
                cur.execute("INSERT INTO users(id,email,username,hashed_password,role,is_active) VALUES (%s,%s,%s,%s,'customer',true)",
                    (uid,row['email'],row['username'],hash_password(secrets.token_urlsafe(48))))
        bind(conn,trusted_issuer=issuer,issuer=issuer,subject=row['subject'],user_id=uid,
             reviewed_by=row['reviewed_by'],review_reference=row['review_reference'])
    return len(report['changes'])


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('manifest');p.add_argument('--apply',action='store_true')
    p.add_argument('--approved-digest');args=p.parse_args()
    from deployment.common import configure_application
    configure_application(migration=True)
    manifest=json.loads(Path(args.manifest).read_text())
    with psycopg2.connect(os.environ['DATABASE_URL']) as conn:
        if args.apply:
            if not args.approved_digest:p.error('--apply requires an operator-approved dry-run digest')
            print('Reviewed changes applied:',apply(conn,os.environ['TRUSTED_IDENTITY_ISSUER'],manifest,args.approved_digest))
        else:
            report,digest=review(conn,os.environ['TRUSTED_IDENTITY_ISSUER'],manifest)
            print(json.dumps({'report':report,'approval_digest':digest},indent=2))
