# P2 execution and acceptance record

Completed 2026-10-08 on `migration/cloud-api-security`, based on approved P1
`d3f537f1dde7550cc946b1d13f2eba3d634d1c9e`. P2 is committed separately; its exact
commit hash is supplied in the completion response (`git log -1 --format=%H`).
No P3/P4, Keycloak integration, Kong JWT validation or business-policy changes.

See [architecture, network matrix, certificate SAN/EKU/trust model and operations](../deployment/p2-tls.md),
[all 227 individual results](p2-case-results.json) and
[negative TLS/rotation evidence](p2-tls-evidence.txt).

## Final run and complete comparison

Project `cloud-api-p2-3f6e70061a6e`, 2026-10-08 00:01:17–00:10:16 UTC
(07:01:17–07:10:16 Asia/Saigon), exit **0**, cleanup **completed**.
Actual main Compose was built and started with isolated project-scoped volumes,
temporary random secrets/PKI and an ephemeral loopback gateway HTTPS publication.
The existing `nginx`, `backend` and `Duck-nettool` deployments stayed running and
their volumes were never attached to the candidate. P2 is validated for deployment;
the pre-existing deployment has not been switched to the candidate.

| Group | Cases | Pass | Expected failures | Unexpected failure/error |
|---|---:|---:|---:|---:|
| P0 JWT/login/refresh/logout | 21 | 19 | 2 | 0 |
| P0 Product/Order/User/RBAC/ownership | 22 | 20 | 2 | 0 |
| P0 migration/template/isolated backup-restore | 3 | 3 | 0 | 0 |
| P0 actual Kong rate limiting (now HTTPS in candidate) | 1 | 1 | 0 | 0 |
| P0 webhook HMAC/timestamp and SSRF | 42 | 39 | 3 | 0 |
| P1 DB privileges and existing-DB adoption | 19 | 19 | 0 | 0 |
| P1 deployment/network/readiness/monitoring/image checks | 16 | 16 | 0 | 0 |
| **Preserved P0/P1 subtotal** | **124** | **117** | **7** | **0** |
| P2 TLS sockets/certificate assertions | 22 | 22 | 0 | 0 |
| P2 HTTPS business/auth/webhook/SSRF | 65 | 59 | 6 | 0 |
| P2 actual Kong/host/Vite/enrollment/rotation/recovery | 16 | 16 | 0 | 0 |
| **Total executions** | **227** | **214** | **13** | **0** |

Original P0: **82 pass + 7 expected failures**. Approved P1: **117 pass + 7
expected failures**. P2 preserves those exact subtotals and adds **97 passes + 6
expected-failure re-executions**. There are **seven unique existing defects**, not
13 new defects. No existing expected failure became a pass. All seven decorators,
test functions and their three source files were compared to approved P1 and remain
unchanged. App auth/routes/models/main and the initial Alembic migration have no diff.

Final pytest baseline: 108 collected, 101 passed/7 xfailed, **24.786 seconds**.
P1 host checks: 16 passed, **57.452 seconds**. P2 pytest: 87 collected,
81 passed/6 xfailed, **210.331 seconds**. P2 host checks: 16 passed,
**199.027 seconds**. The P0 Starlette/AnyIO and Passlib `crypt` deprecation warnings
remain; P2's final report-format warning was removed by selecting compatible JUnit
legacy output for TLS evidence properties. Frontend `npm run build` also passed
(Vite 6.4.3, 1646 modules). Python compilation, staged diff whitespace and staged
private-key/secret-path guards passed.

## TLS and recovery evidence

| Scenario | Observed result |
|---|---|
| Enrolled Kong client, valid server chain/SAN | HTTP 200; TLS1.2 and TLS1.3 |
| Missing/untrusted/expired/unenrolled/wrong-EKU clients | TLS/SSL closure or error before HTTP, both protocol versions |
| Expired client explicitly added to trusted leaf pins | TLS closure; no HTTP response |
| Server-only EKU client explicitly enrolled | TLS closure; no HTTP response |
| Actual Kong using expired or untrusted client | Backend handshake fails; gateway HTTP 502 |
| Actual Kong, backend SAN other.internal but CN backend | Rejected: `upstream SSL certificate does not match "backend"`; HTTP 502 |
| Actual Kong, invalid server issuer chain | Rejected: error 21 `unable to verify the first certificate`; HTTP 502 |
| Actual Kong, expired server | Rejected: error 10 `certificate has expired`; HTTP 502 |
| Actual Kong, clientAuth-only server leaf | Rejected: error 26 `unsuitable certificate purpose`; HTTP 502 |
| Generic verified TLS client, incorrect server hostname | `SSLCertVerificationError`, hostname mismatch |
| Plain HTTP to backend :8443 | No HTTP response |
| Old backend :8000 / gateway :8000 | Connection refused |
| CA accidentally placed in enrollment pin store | Backend startup refused before binding listener |
| Wrong client SAN or untrusted issuer enrolled in pins | Backend startup refused before binding listener |
| Published HTTPS listener | Host Python verifies edge CA + localhost SAN; HTTP 200 |
| Actual Vite proxy | Correct Node extra CA: 200; wrong CA: TLS failure / proxy 500 |
| Leaf renewal | Existing issuers preserved, new leaf keys; overwrite refused |
| CA/client/server rotation | Old, overlapping and mixed generations work; new-only peers work |
| Retired, previously enrolled old Kong client | TLS closure; no HTTP response |
| Edge CA rotation | New trust works; old-only trust raises certificate-verification failure |
| Matching original cert/key/trust rollback | HTTP 200; readiness/products work; missing JWT remains 401 |

Uvicorn/uvloop may close an invalid handshake without forwarding the OpenSSL alert
text. The client therefore sees e.g. `SSLZeroReturnError: TLS/SSL connection has been
closed (EOF)`, rather than a certificate-specific alert. These socket tests read the
connection and establish **no HTTP status or application body**. The explicit-enrollment
tests ensure expiry and EKU rejection is exercised even when the leaf is trusted.
Kong's server-verifier failures are independently confirmed by its actual TLS error
logs and resulting gateway 502. A normal HTTPS request without JWT returns application
401 **after successful mTLS**; it is not treated as proof of TLS rejection.

All successful gateway probes after rotation/recovery check `/health`,
`/health/ready`, product reads and missing-token enforcement. Full HTTPS business
assertions cover all four roles, Product CRUD, Order creation/list/read/status,
customer A versus B ownership, self/admin User access, DB RBAC/is_active authority,
JWT negatives, refresh rotation/reuse/revocation, login/registration/logout, signed
webhooks and real-DNS SSRF allow/deny cases. The production limiter stays 60/minute;
the HTTPS business test client is spaced with headroom. The P0 gateway test explicitly
exhausts the actual limiter and verifies cross-route 429 + Retry-After over HTTPS.

The P1 network namespace probes again confirmed backend can reach PostgreSQL but
Kong, Keycloak, Loki, Promtail and Grafana cannot, by service DNS and actual DB IP.
Exact memberships, private DB/absent public port, runtime DML/DDL denials, migration
ownership/adoption, clean migrations, isolated backup/restore, readiness during DB
outage/schema mismatch, no migration on restart and real log ingestion passed.
Saved backend/bootstrap/migration/test image layers were scanned for every current
runtime secret **and generated PKI private key**, including compressed layers; none
were found. No production service or final disposable test service mounts offline
CA signing keys. Runtime TLS mounts are read-only and peer private keys are separated.
Logs contained no private key material, runtime credential or complete JWT.

## Existing defects and remaining limits

The unchanged unique defects are D01 signed access JWT without exp accepted;
D02 signed non-UUID subject gives 500; D03 signed non-object webhook JSON gives 500;
D04 webhook replay accepted; D05 IPv4-mapped IPv6 loopback passes the validator;
D06 null product price gives 500; D07 null user role gives 500. Six are repeated
through HTTPS; D05 requires deterministic DNS substitution and stays in the original
P0 in-process test. Exact timestamp-boundary and other DNS/IP-fault cases also remain
in P0; a remote HTTPS process cannot be monkeypatched by the caller. No business
or authentication fix was hidden in P2.

Production public CA issuance/ACME, real public DNS, Windows/browser trust installation,
Linux host ownership/ACL deployment and multi-node rollout were not exercised. Testing
used Windows Docker Desktop/Linux containers, host Python 3.14/Node 24.14.0, Python
3.11 API/test containers, Kong OSS 3.8 and cryptography 46.0.5. There is no live CRL/OCSP
or automatic renewal/expiry alerting; use short-lived leaves and pin removal/restarts.
Rotation has single-node restart downtime. Kong's container health is process health;
use verified gateway `/health/ready` for end-to-end readiness. Local CA keys are
development-only; use a separate production issuer and host/secret protections.
DB/monitoring/independent Keycloak transports are outside P2 TLS scope. API bridge
egress remains available as explicitly approved in P1; membership is not a firewall.
The Docker host/daemon and Promtail's existing read-only log filesystem access remain
trusted. These limits are also addressed in the deployment/rotation document.

## Commands executed and reproducibility

Primary commands (repository root unless stated otherwise):

```powershell
python tests/p2/run.py
# Final invocation saved its console to ignored local artifacts:
python tests/p2/run.py *> tests/p2/artifacts/final-console.txt
python -m compileall -q backend/deployment docker/pki.py tests/p2
# From frontend/:
npm run build
# Git commands use command-local safe.directory for this Windows checkout:
git -c safe.directory=D:/MatMaHoc/Project_CLOUD_API diff --check
git -c safe.directory=D:/MatMaHoc/Project_CLOUD_API diff --cached --check
git -c safe.directory=D:/MatMaHoc/Project_CLOUD_API diff d3f537f1dde7550cc946b1d13f2eba3d634d1c9e -- backend/app backend/main.py backend/alembic/versions
```

The final runner recorded **192 exact subprocess argument lists** in ignored local
`tests/p2/artifacts/commands.json` (no secret environment contents). It invoked actual
Compose `build`, `up -d --wait --wait-timeout 300`, test-service runs for P0/P1 and P2,
`ps/inspect/config`, Docker network-namespace probes, image save/layer scans,
PostgreSQL readiness probes, service restarts and `down --volumes --remove-orphans`.
Its prefix uses `--env-file NUL -p cloud-api-p2-3f6e70061a6e` and the main, P1 and P2
Compose files. Host issuance uses `docker/generate_secrets.py --new-deployment` into
a temporary directory and `docker/pki.py`'s generator with negative fixtures; renewal
and CA rotation invoke the same generator. Actual Vite processes were started and
terminated against the candidate's inspected ephemeral HTTPS port, with CA verification
enabled. Git/rg inventory, source/AST comparisons and staged private-key/path scanning
were also executed. Reproduce all deployment/testing commands with the runner;
temporary credentials are intentionally gone after cleanup.

Three complete candidate runner invocations occurred:

1. `cloud-api-p2-9da5588624ac`: baseline 117 pass/7 expected failures; P2 pytest
   78 pass/6 expected failures/3 failures from the new traffic harness hitting the
   unchanged rate limit. Host checks: 8/14 pass, 3 errors and 3 assertion failures.
   Test-only corrections: add request spacing/headroom; read assigned published port
   from NetworkSettings instead of the empty dynamic HostConfig port; recognize
   real OpenSSL error wording and TLS EOF rather than requiring a forwarded alert.
   No production verification or rate-limit setting was weakened. Cleanup completed.
2. `cloud-api-p2-04c94595e8f3`: 214 pass/13 expected-failure executions, no unexpected
   failure/error, cleanup completed. Included CA/SAN/issuer enrollment startup guards.
3. Final project above: same successful 227-case totals with the stricter matching-CN
   wrong-SAN case, compatible evidence output, offline signing keys excluded even
   from test mounts, and expanded gateway readiness/business recovery assertions.

## Exact file inventory and diff summary

Modified:

```text
.gitignore
README.md
backend/Dockerfile
backend/deployment/serve.py
backend/nginx/default.conf
backend/requirements.txt
docker/.env.example
docker/docker-compose.yml
docs/deployment/compose-mtls.reference.yml
frontend/.env.example
frontend/vite.config.js
gateway/kong.yml
tests/p0/compose.yml
tests/p0/test_gateway.py
tests/p1/compose.yml
tests/p1/host_checks.py
tests/p1/run.py
```

Created:

```text
backend/deployment/health.py
backend/deployment/tls.py
docker/pki.py
docker/pki-requirements.txt
docs/deployment/p2-tls.md
docs/testing/p2-results.md
docs/testing/p2-case-results.json
docs/testing/p2-tls-evidence.txt
tests/p0/kong.baseline.yml
tests/p0/transport.py
tests/p2/Dockerfile
tests/p2/Dockerfile.dockerignore
tests/p2/README.md
tests/p2/compose.yml
tests/p2/host_checks.py
tests/p2/launch.py
tests/p2/run.py
tests/p2/test_https_business.py
tests/p2/test_tls.py
```

Diff summary: **36 files changed, 2702 insertions, 33 deletions**.
App business/auth/ORM/initial-migration files and P1 DB privilege/migration implementations
remain unchanged. Cryptography is explicitly pinned for the new certificate-enrollment
API. Historical Nginx/Compose examples are labelled incompatible references, and the
standalone P0 HTTP declaration is explicitly a disposable historical fixture. Test
reports/temp PKI/build outputs are ignored. Existing unrelated untracked documents
were not staged. No generated certificate, private key, token or production credential
is committed. Certificate rotation/rollback instructions are in the deployment document;
P2 source rollback to plaintext P1 is not an approved recovery procedure.
