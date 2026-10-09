# P4 candidate, reviewed accounts and release rollback

Approved base is P3 DNS-evidence commit
`e6501b4d64e428e503db5ae2e624e8188ff8bfd7`; its P3 implementation is
`56af7f81b123fcbe649c70dc88ce6421d6636c48`. This phase changes only a disposable
candidate. No existing deployment, database volume, account or credentials were
cut over. A conditional test result is not production approval.

## Candidate and realm policy

Apply `docker/p4-compose.yml` after the main Compose file. The overlay selects
`AUTH_MODE=oidc`, grants only mapping SELECT to runtime, mounts identity public CA
trust and uses a generated public-key Kong release. The unchanged main declaration
and P3 realm remain available for historical regression. No schema columns or
legacy credentials/refresh records are deleted. Alembic remains at
`0002_external_identities`; no P4 revision is required.

The reproducible P4 realm is `docker/keycloak/florasecure-p4-realm.json`.
Realm `florasecure`, public client `florasecure-spa`, code flow only, required PKCE
S256; implicit, password grant and service accounts disabled. Access lifespan 300
seconds, idle/max SSO policy and rotating refresh/reuse-zero policy retain P3's
values. RS256 and API audience `florasecure-api` retain P3 semantics. Registration
remains disabled. New accounts require reviewed provisioning. No users/passwords
are committed in either realm.

Development redirect URIs are exact HTTPS localhost callback endpoints at ports
5173 and 5174, plus the reserved 5173 silent-check page. The current adapter does
not enable a silent-check page. Web origins are those exact two HTTPS origins;
post-logout redirects are exact `/login` endpoints at those ports. Replace these
development values with reviewed real HTTPS URLs for a deployment. The issuer is
the single stable `IDENTITY_HOSTNAME/realms/florasecure`; configure browser
`VITE_OIDC_URL` with the same reachable origin. Do not use a private alternative
issuer just for the backend. TLS certificates must match every verified hostname.

**Existing persistent realm imports are skipped by Keycloak.** An existing P3
realm therefore needs an operator-reviewed SPA-client update before cutover.
Read its client representation at the private admin interface, compare it with
the P4 source, and update only the reviewed exact `redirectUris`, `webOrigins` and
merged attributes `pkce.code.challenge.method=S256` and
`post.logout.redirect.uris`. Preserve client ID, users and existing audience mapper;
verify all flow flags/session policies against the source. Export and securely
back up the previous client representation first. Use a named least-privilege
realm operator with interactive credential entry or protected runtime files;
never expose admin/master endpoints through the public identity edge. This
operator action was not executed against existing data and remains a cutover
prerequisite. Do not replace/reimport a populated realm as a migration shortcut.

## Reviewed application account mapping

The P3 table remains authoritative:

| Column / constraint | Meaning |
|---|---|
| `issuer` varchar(512), `subject` varchar(255) | Exact trusted realm and Keycloak subject |
| `user_id` UUID FK `users.id`, RESTRICT | Existing application identity |
| `reviewed_by`, `review_reference`, `created_at` | Operator audit metadata |
| Primary key `(issuer,subject)` | One application identity per external identity |
| Unique `(issuer,user_id)` | One subject per application account within issuer |

No lookup by email exists in authentication. Valid unmapped identities receive
401; no user is automatically provisioned. Runtime can SELECT mappings, but cannot
INSERT, UPDATE or DELETE them. Migration credentials and a reviewed manifest are
required for provisioning. Operators retain DB owner power and require external
access controls; application-role assignment remains the existing admin policy.

Prepare a private JSON manifest; use exact application UUIDs from a reviewed
inventory and Keycloak subjects obtained from the trusted private identity admin
interface, not an email match or arbitrary unvalidated token:

```json
[
  {"subject":"reviewed-keycloak-subject","user_id":"reviewed-application-uuid",
   "reviewed_by":"named-operator","review_reference":"approved-change-reference"}
]
```

For a new user, omit `user_id` and explicitly provide reviewed `email` and
`username`. Provisioning creates only an active **customer**, with a fresh UUID
and a random unknown local password. No role field is allowed. Username/email
collisions, duplicated subjects/accounts, ambiguous batches and existing bindings
are rejected. Existing disabled states/roles are preserved when binding old users.

Use an operator-only one-shot migration container, mount the private manifest
read-only and set exact `TRUSTED_IDENTITY_ISSUER`. The job already has the P1
migration secret; do not grant it to the application container. Inside that job:

```sh
python -m deployment.identity_review /review/manifest.json
# Independently review every ID, current role/is_active and proposed operation.
# Only then pass the exact approval_digest from that dry-run report:
python -m deployment.identity_review /review/manifest.json \
  --apply --approved-digest "$APPROVED_REPORT_SHA256"
```

CLI defaults to dry-run and does not write mappings. Apply locks users and mappings,
recomputes the report/digest and rejects changed state or an unapproved digest.
The transaction preserves all existing user and historical order IDs. The explicit
approval value authorizes reviewed data, not automatic email linking. All applied
manifests in this workspace were disposable fixtures, not real account migrations.

## Release cutover and rollback

1. Pass acceptance prerequisites in the test report, restore runtime DNS, and verify
   the full P0–P4 suites in a candidate. Back up both databases and reviewed identity
   inventory; preserve P2 PKI and existing secrets. Review client changes above.
2. Create/import Keycloak users through the trusted operator procedure, including
   secure initial password/reset policy. Never assume a legacy bcrypt hash can be
   silently imported or that matching emails prove identity.
3. Review and apply mapping manifests. Check existing user/order UUID continuity,
   active status, DB roles and unresolved collisions. Keep unmapped users denied.
4. Generate/parse the gateway's verified JWKS release. Build frontend with the exact
   HTTPS issuer, verify login/refresh/logout and `/auth/me`, then activate the
   reviewed P4 overlay. Local token issuance is 410 only in this release; HS256
   legacy tokens are rejected at both layers. No dual-issuer grace period exists.
5. Monitor controlled 401/403/429, IdP availability and current key synchronization.
   Preserve HMAC webhooks, DB RBAC and upstream mTLS throughout.

Rollback is an **explicit release deployment**, never an automatic response to an
authentication failure. Restore the approved P3 release `e6501b4` (including its
legacy frontend, main Kong declaration and migration grant script) with the same
application volume, secrets and PKI. Run its migration/grant job to revoke P4-only
mapping lookup from runtime; keep the additive mapping table and all historical
data. Restore reviewed client settings only if the operator determines they are
needed; do not delete identity volumes/users or alter primary keys. Existing local
password users can use the approved legacy login. Keycloak-only new accounts have
no known legacy password and require an explicitly authorized password reset or
must remain denied during rollback. Clear current browser state/redeploy the
matching frontend. Verify the legacy auth/business and mTLS suites. Rollback
knowingly restores the historical P0-D01/D02 limitations; it is not a recommended
security downgrade without incident/change review.

Legacy refresh records remain schema-compatible but are not consulted in P4.
Keycloak SSO sessions/refresh issuance and old locally verified access tokens have
the revocation limits described in the architecture. SQL TLS, BFF, MFA policy,
HA/backups certification, broader WAF and P5–P7 work are outside this phase.
