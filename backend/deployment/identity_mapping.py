"""Offline P3 operator tool. Never invoked by application authentication.
Trust is exact and operator-controlled; no email or token-claim lookup is accepted.
Requires the migration-role connection and an explicit review record.
"""
import argparse
import os
from urllib.parse import urlsplit
from uuid import UUID
import psycopg2

def bind(connection, *, trusted_issuer, issuer, subject, user_id, reviewed_by, review_reference):
    url = urlsplit(trusted_issuer)
    if (issuer != trusted_issuer or url.scheme != "https" or not url.hostname
            or url.username or url.password or url.query or url.fragment
            or not url.path.startswith("/realms/") or issuer.endswith("/")):
        raise ValueError("Issuer must exactly match the operator-configured trusted realm issuer")
    if not subject or not reviewed_by.strip() or not review_reference.strip():
        raise ValueError("Subject and operator review evidence are required")
    UUID(str(user_id))
    with connection.cursor() as cur:
        cur.execute("INSERT INTO external_identities (issuer,subject,user_id,reviewed_by,review_reference) "
                    "VALUES (%s,%s,%s,%s,%s)", (issuer,subject,str(user_id),reviewed_by,review_reference))
    # No upsert, replacement, role assignment, user creation or email matching.

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("issuer", "subject", "user-id", "reviewed-by", "review-reference"):
        parser.add_argument("--"+name, required=True)
    args = parser.parse_args()
    from deployment.common import configure_application
    configure_application(migration=True)
    with psycopg2.connect(os.environ["DATABASE_URL"]) as conn:
        bind(conn, trusted_issuer=os.environ["TRUSTED_IDENTITY_ISSUER"], issuer=args.issuer,
             subject=args.subject, user_id=args.user_id, reviewed_by=args.reviewed_by,
             review_reference=args.review_reference)
    print("Reviewed identity binding created")
