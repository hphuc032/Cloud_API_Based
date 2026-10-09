# P3 identity preparation: implementation and test record

## P4-worktree compatibility revalidation — 2026-10-09 UTC

This file retains the historical P3 record below. The separately authorized P4
candidate is described in [P4 results](p4-results.md); historical "no P4"/"stop"
statements below refer to the scope at the time of P3's original validation.
P3 acceptance is still **BLOCKED**, not promoted by a P4 commit.

The full unchanged historical test groups were rerun in explicit legacy mode on
the P4 worktree, project `cloud-api-p3-b69c8dae86ca`,
2026-10-09T06:44:38.454584+00:00–06:56:56.709181+00:00 UTC:
**252 executions, 236 passed, 13 strict expected failures, 2 DNS failures and
1 DNS error; no skipped cases or other failures.** All seven unique baseline
defects remain expected failures. All 25 provider/mapping/persistence checks and
P2's 22 socket plus 16 host mTLS checks passed. Cleanup completed.
The three original DNS test IDs/root cause remain unchanged; fresh Agent/backend
diagnostics and all individual rerun outcomes are in [P4 evidence](p4-evidence.json)
and [case results](p4-case-results.json). This is compatibility evidence for the
P4 worktree in legacy mode, not a rewritten validation of the immutable P3 commit.

Branch: `migration/cloud-api-security`. Approved parent P2:
`16703e01285938c6b8d002b672f2124e8ab24ac1`. Date: 2026-10-08 (Asia/Saigon).
P3 implementation commit: `56af7f81b123fcbe649c70dc88ce6421d6636c48`.
Any acceptance-recovery commit changes documentation/evidence only. No P4 cutover, Kong JWT validation or business-policy
change was implemented. No production deployment or database was changed.

**P3's independent provider/mapping checks pass. Strict phase acceptance remains
blocked by three independently reproduced runtime DNS failures.** Do not classify them
as passes or new P0 expected failures. Restore public DNS in the runtime and rerun
the complete runner before approving strict P3 acceptance.

## Final validation and acceptance recovery — 2026-10-08 UTC

Validated implementation: `56af7f81b123fcbe649c70dc88ce6421d6636c48`.
**Recommendation: BLOCKED.** DNS could not be restored through the supported
runtime interfaces available in this environment. No P4 work was performed.

The focused rerun executed all three affected cases **before** the full suite:
**0 passed, 2 failed, 1 error, 0 expected failures, 0 skipped**. Both staff/admin
requests traversed verified HTTPS and Kong upstream mTLS and returned exactly
`400 {"detail":"Unable to resolve hostname"}`. No certificate checks or assertions
were changed. The temporary recovery driver selected existing tests once, restored
the unittest loader, then ran the complete unchanged runner sequence with fresh
project-scoped databases and volumes. Selection did not disable any full-suite test.

The fresh full run is `cloud-api-p3-68308dcfa0da`, 2026-10-08T05:00:29.864250+00:00–2026-10-08T05:19:29.728807+00:00 UTC, exit 1;
project containers, networks and volumes were removed successfully. This is one
complete current run, rather than the historical combined runs below.

| Group | Executed | Passed | Expected failure | Failure/error |
|---|---:|---:|---:|---:|
| P0 auth/business/webhook/SSRF/schema | 89 | 82 | 7 | 0 |
| P1 database privileges and populated-DB adoption | 19 | 19 | 0 | 0 |
| P1 deployment/network/readiness/monitoring/image checks | 16 | 15 | 0 | 1 DNS error |
| P2 TLS socket/certificate checks | 22 | 22 | 0 | 0 |
| P2 HTTPS auth/business/webhook/SSRF | 65 | 57 | 6 | 2 DNS failures |
| P2 Kong/TLS/enrollment/rotation/recovery/Vite checks | 16 | 16 | 0 | 0 |
| P3 OIDC and identity-mapping cases | 22 | 22 | 0 | 0 |
| P3 identity isolation/privileges/restart | 3 | 3 | 0 | 0 |
| **Total** | **252** | **236** | **13** | **3 DNS** |

Separately rerun: **19 inactive-client assertions passed**, frontend production
build **passed** (4.01 seconds). There were **0 unexpected passes, 0 skipped or
disabled cases, and 0 unexecuted cases in the requested suite**. The three DNS
failures remain unexpected test outcomes; they are not xfails. The required
post-DNS-restoration focused/full rerun is **unexecuted and blocked**; this fresh
diagnostic full run does not satisfy that prerequisite. There were no other
unexpected failures. The seven unique defects P0-D01–D07 remain strict expected
failures, re-executed 13 times across the suites.

### Exact failures and root cause

| Test ID and source | Assertion/query | Actual result and cause |
|---|---|---|
| `host_checks.execute.<locals>.DeploymentChecks.test_public_dns_for_current_ssrf_validation`, `tests/p1/host_checks.py:152` | Backend network namespace: `bool(socket.getaddrinfo('example.com',443))` prints `True` | `socket.gaierror: [Errno -3] Temporary failure in name resolution`; probe subprocess exits 1, causing `CalledProcessError` and a unittest error. Supplied runtime upstream DNS endpoint is unavailable. |
| `tests/p2/test_https_business.py::test_https_ssrf_uses_real_dns_and_preserves_roles[staff-200]`, line 72 | HTTPS `POST /api/v1/security/fetch-url`, `url=https://example.com/test`, status must be 200; validator calls `socket.getaddrinfo('example.com',None)` | Status 400, `Unable to resolve hostname`, then `AssertionError`. Same upstream DNS failure; staff authorization reached the unchanged validator. |
| `tests/p2/test_https_business.py::test_https_ssrf_uses_real_dns_and_preserves_roles[admin-200]`, line 72 | Same request/query, authorized admin, status must be 200 | Same 400/error and root cause. |

All three require `example.com` A/AAAA resolution. Independent raw DNS diagnostics
also queried `pypi.org` as an allowed control domain:

- Agent resolver: `/etc/resolv.conf` supplies `172.31.0.93`. Connected UDP and TCP
  to port 53 return `[Errno 111] Connection refused`. Unconnected UDP waits time
  out. Neither A nor AAAA queries produce answers.
- Actual backend resolver: Docker `127.0.0.11`, with upstream
  `host(172.31.0.93)`, no overrides. It returns **SERVFAIL (rcode 2), zero answers**
  for both domains/types, over both UDP and TCP. Real backend `getaddrinfo` and
  probes sharing backend/Kong namespaces also fail for external names.
- Internal Docker names work: the backend resolves `postgres` and `kong` to their
  project network addresses. The full isolation tests exercise both names and real
  database IPs. `api_transport` has `Internal=false`; data/observability networks
  retain `Internal=true`. This is not P1's earlier all-internal API network defect.
- Default-verified HTTPS to `https://pypi.org` through the platform proxy returns
  200; `https://example.com` receives proxy tunnel 403 under the original policy.
  Internet/proxy availability therefore does not imply libc/raw DNS availability.
- Read-only host firewall inspection was denied. Platform resolver listener,
  sidecar and firewall state are not exposed. We can locate the failing upstream
  resolver path, but cannot distinguish an absent listener from platform-side
  rejection, or establish a global authoritative-DNS outage.

Classification for each failure: **execution-environment DNS infrastructure**;
no application regression or incorrect Compose network isolation was detected.
The SSRF validator's SHA-256 is
`b84670ffa50dca7510bbea1f33dc58a323fc00445e041053e7c5765429495ad3` in P1,
P2 and P3. P1's final 16 deployment checks passed; approved P2 had
**214 passed / 13 expected failures / 0 failures (227 executions)**. The fresh
historical portion here has **211 passed / 13 expected failures / 3 DNS failures**.
P3 adds 25 passing executions. Existing auth/business routes, defect tests, main
application and P2 Kong declaration remain unchanged; no DNS exception was loosened.
P0/P1 authority/privilege checks, P2 negative certificate/mTLS/rotation checks and
local login/JWT/refresh/logout/ownership checks passed. P3 still rejects a genuine
Keycloak token in the current application, including after explicit identity mapping.

### Supported recovery attempted and remaining blocker

The environment draft now preserves its `package_managers` preset and adds only
`example.com` to custom destinations. Reusable startup instructions now describe
P3 validation and the raw-DNS prerequisite. The configuration tool confirms **saved,
requires publication**; it cannot apply or repair the running resolver. A post-save
`getaddrinfo('example.com',443)` still fails with errno -3. No public resolver IP,
fixed host answer, proxy-based DNS substitute, firewall change, TLS bypass,
authentication cutover or application/test/deployment configuration change was introduced.

Required external action: review/save the destination and startup draft in environment
settings and publish as required by the tool, and have the supported runtime restore
a working DNS resolver reachable by the Agent and Docker. Domain allowlisting alone
is insufficient evidence of DNS repair. Alternatively run on a supported environment
with functioning raw DNS. Once both host and backend `getaddrinfo` succeed, rerun the
same three cases first and then the full suite. Until then, P3 acceptance stays pending.

### Commands and evidence

The public [DNS recovery evidence](p3-dns-recovery-evidence.json) records queries,
errors, resolver files, network flags, source hashes, response bodies and focused
results. [Individual case results](p3-case-results.json) now contain this complete
fresh run; [command inventory](p3-commands.json) retains historical commands and adds
`acceptance_recovery`. Discovery/JWKS and TLS evidence were refreshed from this run.
Local raw diagnostics remain under `/workspace/.cloud-api/p3-dns-recovery/` and are
not required production configuration.

Principal executed diagnostics/validation commands:

```text
cat /etc/resolv.conf
ip route
ss -lunt
iptables -S; iptables -t nat -S  # denied; also retried with a writable lock path
python3 /workspace/.cloud-api/p3-dns-recovery/dns_probe.py
# Python socket probes: connected UDP/TCP to supplied resolver, getaddrinfo,
# actual backend docker exec, and docker run --network container:<backend/Kong>.
# Python urllib default-verified HTTPS proxy controls for example.com and pypi.org.
docker network inspect cloud-api-p3-68308dcfa0da_<network>
git show <P1/P2/P3>:<security/defect-test path>  # SHA-256 comparison
docker system df
docker image rm cloud-api-p3-tests-base:verified cloud-api-p3-backend-base:verified
# Replaced these redundant local cache bases with aliases to source-verified
# retained test/backend images, avoiding duplicated vfs storage; no service data removed.
docker image tag cloud-api-p3-9a389b7320a8-tests cloud-api-p3-tests-base:verified
docker image tag cloud-api-p3-9a389b7320a8-backend cloud-api-p3-backend-base:verified
DOCKER_CONFIG=/workspace/.docker-config P3_REUSE_PROJECT_IMAGES=cloud-api-p3-9a389b7320a8 python3 /workspace/.cloud-api/p3-dns-recovery/run_recovery.py
node tests/p3/test_client.mjs
npm --prefix frontend run build
```

The local recovery driver is the committed `tests/p3/run.py` with the checkout/output
paths made explicit and a focused-test/diagnostic step inserted before its full-suite
sequence. It neither changes production Compose nor changes test assertions. Source
hash checks confirmed reused container code/realm matches the P3 checkout. All data,
secrets, PKI and project networks were disposable. Original development services
were preserved. Only tracked documentation/evidence changed for this recovery.

Tracked recovery files: `docs/testing/p3-results.md`, `p3-case-results.json`,
`p3-commands.json`, `p3-oidc-evidence.json`, and new
`p3-dns-recovery-evidence.json` (all under `docs/testing/`).
No application, test, deployment configuration, certificate-verification or
business-authorization files changed.

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

## Historical implementation results

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
| **Historical combined outcomes** | **252** | **236** | **13** | **3 environmental** |

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
