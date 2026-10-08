# P3 identity preparation: implementation and test record

Branch: `migration/cloud-api-security`. Approved parent P2:
`16703e01285938c6b8d002b672f2124e8ab24ac1`. Date: 2026-10-08 (Asia/Saigon).
P3 is committed separately; its exact commit is in the completion response and
`git log -1 --format=%H`. No P4 cutover, Kong JWT validation or business-policy
change was implemented. No production deployment or database was changed.

**P3's independent provider/mapping checks pass. Strict phase acceptance remains
blocked by three confirmed cloud DNS regression failures.** Do not classify them
as passes or new P0 expected failures. Restore public DNS in the runtime and rerun
the complete runner before approving strict P3 acceptance.

## Architecture, configuration, schema and operations

The [P3 design](../deployment/p3-identity.md) contains the final Mermaid architecture,
realm/client settings, runtime-secret and certificate requirements, exact mapping
schema, operator review procedure, migration/downgrade and recovery instructions.
Keycloak uses production `start`, stable HTTPS hostname, verified HTTPS readiness,
a separate persistent PostgreSQL instance, and a non-superuser database owner.
A restricted HTTPS identity proxy exposes the realm/login resources; admin, master
realm and management endpoints are private. Neither database publishes a port.
Application Kong HTTPS and verified mutual TLS remain unchanged.

The public SPA uses code + mandatory PKCE S256, exact HTTPS callback/origin, RS256,
300-second access tokens, 30-minute idle/eight-hour maximum sessions and refresh
rotation with zero reuse. `basic`, `profile`, and `email` are default client scopes;
`basic` is required to include the access-token subject. Access audience is
`florasecure-api`; ID-token audience is `florasecure-spa`. Registration/password reset,
implicit/hybrid, password and service-account flows are disabled for the SPA.
No realm users or passwords are committed.

The additive mapping table uses `(issuer, subject)` as its primary key,
`UNIQUE(issuer, user_id)`, and a restricting FK to the existing `users.id`.
Review metadata is mandatory. Existing application UUIDs, roles, active flags and
Order/Product/User relationships are unchanged. The offline operator tool verifies
an exact configured trusted HTTPS issuer; it never looks up/link accounts by email,
creates users, changes roles or upserts conflicts. Runtime access to the inactive
mapping table is denied. ORM metadata is registered for Alembic without auth wiring.

## Executed results

Full regression project: `cloud-api-p3-74c90e2fd3fc`,
10:15:28–10:32:52 Asia/Saigon (03:15:28–03:32:52 UTC), wrapper exit 1,
cleanup completed. Final corrected P3 project: `cloud-api-p3-9a389b7320a8`,
10:58:21–11:03:08 Asia/Saigon (03:58:21–04:03:08 UTC), wrapper exit 0,
cleanup completed. Results below combine the full historical regression with the
final corrected P3 rerun; they are not a claim of one all-green full run.

| Group | Executed | Passed | Expected failure | Failure/error |
|---|---:|---:|---:|---:|
| P0 unchanged auth/business/webhook/SSRF and additive schema regression | 89 | 82 | 7 | 0 |
| P1 privileges and historical populated-DB adoption | 19 | 19 | 0 | 0 |
| P1 actual deployment/network/readiness/monitoring/image checks | 16 | 15 | 0 | 1 DNS error |
| P2 TLS socket/certificate checks | 22 | 22 | 0 | 0 |
| P2 HTTPS auth/business/webhook/SSRF | 65 | 57 | 6 | 2 DNS failures |
| P2 actual Kong/TLS/enrollment/rotation/recovery/Vite checks | 16 | 16 | 0 | 0 |
| P3 real OIDC and mapping/migration cases | 22 | 22 | 0 | 0 |
| P3 identity isolation/privileges/restart checks | 3 | 3 | 0 | 0 |
| **Combined final outcomes** | **252** | **236** | **13** | **3 environmental** |

Separately, the inactive client module passed **19 Node assertions** covering valid
responses and exact callback/state/nonce/issuer/audience/expiry rejection. The
frontend production build passed: Vite 6.4.3, 1646 modules. All requested test cases
were executed; no required tests were skipped, disabled or left unrun after the
corrected P3 rerun. Optional full browser UI/cutover, production certificate deployment,
HA/load/disaster recovery, database encryption and current CVE auditing were not run.

The 13 expected failures are re-executions of the **same seven unique P0 defects**.
The three defect-source files are byte-for-byte unchanged from approved P2; no
expected failure was converted to a pass or loosened. Existing authentication,
routes, services, User/Order/Product/RefreshToken models, main application, initial
migration and Kong declaration have no diff from P2. Historical schema assertions
were adjusted explicitly for the new head/table/eighth FK. Adoption still begins
at the original initial revision and compares every populated application row and
relationship before/after upgrade, while checking the new revision separately.

### Remaining environment failures

1. P1 `test_public_dns_for_current_ssrf_validation`: `getaddrinfo('example.com',443)`
   raises `socket.gaierror: Temporary failure in name resolution`.
2. P2 `test_https_ssrf_uses_real_dns_and_preserves_roles[staff-200]`.
3. P2 `test_https_ssrf_uses_real_dns_and_preserves_roles[admin-200]`.

The latter requests return HTTP 400 because the existing validator cannot resolve
its allowlisted public hostname. The same host resolution fails outside Docker and
outside the shell sandbox. Docker service-name resolution works; all provider HTTPS
and application transport checks pass. These are diagnosed runtime DNS failures,
not permissions, credentials, new authorization policy or P3 code defects. No fake
DNS records, assertion changes or new xfail decorators were used to hide them.
There are zero unexplained final P3 failures, but these three failures still block
strict full-regression acceptance.

### Comparison with approved P2

Approved P2: **227 executions, 214 passed / 13 expected failures / 0 failures**.
This cloud's historical regression: **227 executions, 211 passed / 13 expected
failures / 3 diagnosed DNS failures**. P3 adds **25 passing executions**, plus the
19 separate client assertions. Local login/JWT/refresh/logout, PostgreSQL-authoritative
RBAC/is_active, ownership and P2 HTTPS/mTLS remain unchanged and passed. A genuine
Keycloak RS256 token still receives 401 from the current application even after its
verified issuer/sub has been explicitly bound to an existing application user.

## Discovery, signing and schema evidence

- [Verified HTTPS discovery and public JWKS](p3-oidc-evidence.json).
- [Verified token summary, without tokens or nonce values](p3-token-verification-evidence.json).
- [Actual mapping columns and PostgreSQL constraints](p3-identity-schema.json).
- [All 252 individual final case outcomes](p3-case-results.json).
- [P2 negative TLS, rotation, rollback and Vite evidence](p3-tls-evidence.txt).
- [Detailed executed Docker commands](p3-commands.json); temporary paths are labelled.

Observed issuer: `https://identity-edge:8443/realms/florasecure` in the isolated
project. HTTPS discovery/JWKS chain and hostname were verified. RS256 access/ID token
signatures, exact issuer/audiences, 300-second lifetime, nonce and ID-token at_hash
were verified. The subject matches the actual created Keycloak user and the reviewed
binding preserves the unrelated existing application UUID. Normal refresh works;
old refresh and authorization codes are rejected after reuse. Wrong PKCE, missing/
plain PKCE, incorrect redirects and prohibited SPA grants/response types are rejected.

Actual restart checks preserve user subject, a deliberately edited realm setting,
SPA configuration and signing keys across both identity PostgreSQL and Keycloak
restart. Identity database role flags are all nonprivileged; no DB/admin/management
port is published. Backend/Kong/identity proxy/application DB/Grafana cannot reach
the identity DB by name or IP; Keycloak can. Unsafe HTTP hostname configuration is
rejected before launching Keycloak. Public admin/master/management routes return 404.

## Commands and resolved iterations

Repository-root commands included:

```sh
git ls-remote --heads origin
git fetch origin migration/cloud-api-security
git switch -c migration/cloud-api-security FETCH_HEAD
backend/.venv/bin/pip install --cache-dir /workspace/.pip-cache -r backend/requirements.txt
node tests/p3/test_client.mjs
npm run build --prefix frontend
backend/.venv/bin/python tests/p3/run.py
backend/.venv/bin/python tests/p3/run.py --identity-only
```

Cloud invocations additionally set `DOCKER_CONFIG=/workspace/.docker-config` and
`P3_BUILD_OVERLAY=/workspace/.cloud-api/cloud-build.json`. Package installation used
the supplied proxy, its trusted CA and normal artifact/signature verification.
The local test-image apt preparation omitted an unrelated PGDG update source; the
existing PostgreSQL client binaries came from the verified official base image.
No TLS, package signature or checksum check was disabled.

Docker's `vfs` driver on this 32-GB cloud workspace duplicated image/build/container
filesystems. Verified dependency images were locally flattened with `docker create`,
`docker export`, `docker import`, and obsolete **own test image tags** were removed;
unused builder cache was released. These operations did not remove unrelated images,
services or volumes. The final run reused the unchanged prepared images with
`P3_REUSE_PROJECT_IMAGES=cloud-api-p3-2197814b16c7`; SHA-256 comparisons of every
container-executed Python source and realm JSON passed, and application/job image
filesystem equality was checked. All services started against new isolated volumes;
no test was substituted or skipped. The committed Dockerfile remains a normal,
independently reproducible build on a host with adequate resources and connectivity.

Earlier attempts were not accepted and were superseded by diagnosed reruns:

- Read-only home Docker/npm caches, Docker proxy DNS/trust, missing build-context
  include rules, nonroot public-config readability and VFS disk exhaustion were
  corrected as setup issues. Temporary secret mounts retain private host-parent
  protection and per-service assignments.
- The ID-token test initially omitted access_token when verifying at_hash; supplying
  it preserved rather than disabled hash/signature checks.
- The initial realm omitted basic scope and access tokens lacked sub. The realm was
  corrected, not the required subject assertion.
- A deliberate authorization-code replay preceded normal refresh and invalidated its
  grant/session. Normal refresh/rotation is now exercised before replay negatives.
- DiskFull caused 19 fixture errors in later attempts. The final rerun had sufficient
  space and completed all 22 integration/three infrastructure checks successfully.

Detailed commands, public evidence and final per-case outcomes are saved in Git;
full logs/inspection metadata/intermediate diagnostics are ignored local artifacts.
All disposable project containers, networks and database volumes were cleaned up.
The unrelated onboarding PostgreSQL instance was preserved.

## Files and security limitations

Modified: `.gitignore`; `backend/app/models/__init__.py`;
`backend/deployment/common.py`; `docker/.env.example`, `docker/docker-compose.yml`,
`docker/generate_secrets.py`, `docker/keycloak-entrypoint.sh`;
`tests/p0/test_database.py`; `tests/p1/host_checks.py`, `test_adoption.py`,
`test_privileges.py`.

Created: `backend/alembic/versions/0002_external_identities.py`;
`backend/app/models/external_identity.py`;
`backend/deployment/identity_bootstrap.py`, `identity_mapping.py`;
`docker/keycloak/HealthProbe.java`, `florasecure-realm.json`, `nginx.conf`;
`frontend/src/identity/oidcPreparation.js`;
`tests/p3/{Dockerfile,Dockerfile.dockerignore,README.md,compose.yml,host_checks.py,
launch.py,persistence.py,pki.py,run.py,test_client.mjs,test_identity.py}`;
`docs/deployment/p3-identity.md`; this report and the six linked evidence/command
files under `docs/testing/p3-*`.

No production secrets, runtime token/nonce values, private keys, credential values
or user database exports are committed. Identity images are digest-pinned: Keycloak 26.2.5
`sha256:4883630ef9db14031cde3e60700c9a9a8eaf1b5c24db1589d6a2d43de38ba2a9`,
Nginx `sha256:65645c7bb6a0661892a8b03b89d0743208a18dd2f3f17a54ef4b76fb8e2f2a10`,
identity PostgreSQL `sha256:ca0bd484cb98bf4b24eb1010e73fb3fcbd6714d240fbc1a10eea5b7dbecb641d`.
Pinning/test success does not certify these older releases against current CVEs.

Before production operation, provision reviewed real HTTPS origins/certificates,
secure reader ACLs/vault integration, named administrative accounts, backups and
credential/key renewal. Compose secret files are mounts, not a vault. Identity DB
traffic is private-network PostgreSQL; SQL TLS, at-rest encryption, HA and recovery
objectives are not configured/certified here. DB owners/operators can bypass the
binding tool and require independent access control/audit. P2's development H2
identity volume is not automatically migrated or deleted; archive/export any needed
lab identities separately before adoption. Existing application localStorage/session
limitations and seven P0 defects remain unchanged. The client preparation helpers
are inactive contracts, not a complete browser OIDC implementation or JWT verifier.

Git diff summary: **38 files changed, 8721 insertions, 25 deletions**.
Most additions are detailed command/case evidence.

P3 is an independently tested identity preparation change. **Do not start P4.**
