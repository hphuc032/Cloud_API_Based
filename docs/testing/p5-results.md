# P5 security hardening — acceptance report

**Recommendation: CONDITIONAL. Strict real-DNS acceptance remains BLOCKED.** The implemented controls and corrected browser flows passed their executed checks. Three distinct unchanged DNS cases still fail in this environment; they were not mocked into passing, skipped, disabled or converted to xfails. No production rollout or push from Workspace A is authorized or performed.

Approved parent: `11136585a0bade4144976bd3a0500d6f36503f28`, tree `6893c2e6c724faa2dc93da46203d32b087df9f40`. Before P5, the earlier `f48dff3137c72f3640cc0cdd86d9eeef60aa1d4a` was verified to have the same parent/tree and no content difference. Fetch on 2026-10-21 confirmed the current branch and origin matched the approved P4 base. Existing P0–P4 commits were not rewritten. The exact resulting P5 commit/tree and verified bundle digest are recorded in the external transfer manifest beside the bundle, avoiding a self-referential commit hash inside this report.

## Implemented controls

See [architecture, threat/access matrix, migration and rollback](../security/p5-design.md). P5 adds atomic provider-scoped webhook receipts, strict raw-body HMAC/event validation, bounded rotation, global-unicast DNS classification, controlled input validation, supported Kong OSS pre-JWT endpoint budgets, consistent API headers, exact CORS, Keycloak brute-force policy, and a verified HTTPS production SPA boundary with strict CSP. Security Center uses actual responses; fabricated monitoring statistics and stale links were removed. Frontend MAC delivery preserves boundary whitespace. SPA access logs omit OAuth callback/query values.

The FastAPI auth modules, local-auth implementation, order policies, TLS server/enrollment code, base Compose networks and migrations 0001/0002 are unchanged from P4. Active P5 explicitly inherits the P4 **OIDC** overlay; legacy mode is used only in the separate historical regression. Roles, active status and ownership remain PostgreSQL decisions. No email auto-linking, privileged claim assignment, authentication fallback, new identity provider or Enterprise plugin was added.

## Before/after vulnerability matrix

Before proof: frozen approved-P4 source at `/workspace/.cloud-api/p5-baseline-src`, isolated project `cloud-api-p0-f02ced037dcd`, 2026-10-14: **7 strict xfails, 82 deselected**. This was seven selected cases, not a full 89-case suite. Application and assertions preceded P5 changes.

| Defect | Before | Active P4/P5 result | Legacy release in this checkout |
| --- | --- | --- | --- |
| D01 missing exp | Legacy JWT accepted | P4/P5 require OIDC claims; missing expiry rejected | Retained strict expected failure |
| D02 malformed UUID subject | Legacy HTTP 500 | Invalid/unmapped subject controlled 401; issuer/sub lookup preserved | Retained strict expected failure |
| D03 signed non-object JSON | HTTP 500 | HTTP 400, no handler effect | Fixed validation applies here too |
| D04 repeated signed event | Handler acknowledgement repeated without durable deduplication | Authenticated stored 200 retry, one handler/receipt; conflicting ID/body 409 | Same secure receipt implementation |
| D05 mapped IPv6 loopback | Validation accepted 200 | Normalized classification denies 403 | Same fixed validator |
| D06 null product price | HTTP 500 | HTTP 422, unchanged product row | Same fixed schema |
| D07 null user role | HTTP 500 | HTTP 422, unchanged role | Same fixed schema |

The first post-fix project `cloud-api-p5-4be373658d70` passed **75 cases** before D03–D07 xfails were removed. Evidence includes real PostgreSQL, genuine Keycloak tokens, eight concurrent deliveries with one invocation/receipt, failed-effect/receipt rollback followed by retry, old-key retirement and no partial null-field mutations. D04 intentionally replaces the old blanket-409 proposal with compatible idempotent provider retries; equal HTTP status alone is not proof of duplicate processing. D01/D02 assertions remain unchanged.

## Final regression matrix

Counts are **executions per phase**, not unique vulnerabilities. Repeated focused runs and the first 75-case proof are not added as extra unique cases. Browser groups contain several assertions each; the separate P3 client command reports 19 assertions, not 19 additional pytest cases.

| Authoritative phase | Passed | Expected failures | DNS failure/error | Other unresolved failure |
| --- | ---: | ---: | ---: | ---: |
| P5 live webhook, concurrency, schema, SSRF and gateway | 98 | 0 | 0 | 0 |
| P5 pure configuration bounds/rotation validation | 12 | 0 | 0 | 0 |
| P4 OIDC/RBAC/BOLA + P2 TLS + P1 privilege pytest | 143 | 0 | 2 | 0 |
| P4 network/role/observability host | 5 | 0 | 0 | 0 |
| P3 private identity DB/persistence host in candidate | 3 | 0 | 0 | 0 |
| P2 TLS/renewal/proxy host in candidate | 16 | 0 | 0 | 0 |
| Final P4 SDK/browser lifecycle, state/nonce/outage | 9 | 0 | 0 | 0 |
| Final production SPA/CSP/Security Center browser groups | 8 | 0 | 0 | 0 |
| Signing-key rotation/retirement/JWKS outage phases | 6 | 0 | 0 | 0 |
| Separate legacy P0/P1 pytest | 106 | 2 | 0 | 0 |
| Separate legacy P2 HTTPS/mTLS/business pytest | 83 | 2 | 2 | 0 |
| Separate legacy P3 OIDC provider/mapping pytest | 22 | 0 | 0 | 0 |
| Separate legacy P1 host | 15 | 0 | 1 error | 0 |
| Separate legacy P3 persistence host | 3 | 0 | 0 | 0 |
| Separate legacy P2 TLS host | 16 | 0 | 0 | 0 |

Also passed: P4 focused 3/3 (a repeated subset), `node tests/p4/test_session.mjs`, `node tests/p3/test_client.mjs` (19 assertions), frontend production builds, source-hash verification and `git diff --check`. The P5 launcher now selects the three P5 modules; this session executed its 98 integration cases and 12 pure settings cases separately. The legacy P0/P1 phase emitted two warnings, with no failure.

Candidate project: `cloud-api-p5-57662720b576`. Final corrected browser project: `cloud-api-p5-92dc79787452` (2026-10-21 10:21:59–10:25:20 UTC). Legacy project: `cloud-api-p3-5d574e9aa485` (10:09:57–10:21:29 UTC). Cleanup succeeded for all three. Nonzero full-runner exit codes are retained: candidate pytest has two DNS failures; legacy has three; the original candidate production-SPA setup failure was superseded by the successful focused browser rerun, not erased from its run record.

### Regression comparison

Frozen P4 pre-fix candidate: **134 passed / 4 xfailed / 7 failed** in 145 pytest executions. Two failures were DNS; five socket/TLS failures occurred using the local alternative Python 3.11.17/OpenSSL 3.5.7 client image. The final repository-style PostgreSQL test environment uses Python 3.11.2/OpenSSL 3.0.22 and passes the same positive TLS 1.2/1.3 assertions. Negative peer closure can surface BrokenPipeError; only the bad-client test accepts that transport failure, still forbidding any HTTP response. No TLS verification or positive-client expectation changed. Compatibility of every alternative client/OpenSSL combination is not certified.

Final active candidate: **143 passed / 0 xfailed / 2 DNS failures** in the same 145-case phase. Four active defect assertions now pass; deterministic D05 coverage is in P5. Approved historical P0/P1/P2 had 227 executions (214 pass/13 xfail); this environment's earlier baseline was 211 pass/13 xfail/3 DNS failures. Final legacy P0/P1/P2 is **220 pass / 4 xfail / 3 DNS failures** in 227 executions: nine repeated defect executions now pass, representing five unique fixes. The four remaining xfails represent only two unique legacy JWT defects. Adding P3 gives **245 pass / 4 xfail / 3 DNS failures** in 252 legacy executions.

## Exact DNS blocker

| Distinct case | Query / assertion | Actual outcome |
| --- | --- | --- |
| P1 host `test_public_dns_for_current_ssrf_validation` | `socket.getaddrinfo('example.com',443)` must produce addresses in the backend namespace | gaierror errno -3; subprocess exits 1; unittest error |
| P2 `test_https_ssrf_uses_real_dns_and_preserves_roles[staff-200]` | Authorized HTTPS URL-validation request for example.com must return 200 | HTTP 400, `Unable to resolve hostname` |
| P2 `test_https_ssrf_uses_real_dns_and_preserves_roles[admin-200]` | Same for admin | Same HTTP 400 |

The last two cases are executed in both candidate and legacy suites, producing five failed/error executions across three distinct IDs. Roles remain unchanged: anonymous/customer negatives pass. Direct validator diagnosis confirms controlled 400, not a network fetch or allowlist bypass.

Agent `/etc/resolv.conf` specifies `172.31.2.109`; Docker uses embedded `127.0.0.11` forwarding to that host resolver with no overrides. Host example.com and pypi.org getaddrinfo fail; an executed outside-sandbox example.com getaddrinfo query also fails with errno -3. In-sandbox raw A-query diagnostics show UDP timeout after three seconds and TCP connection refused on the configured resolver's port 53. A later outside-sandbox raw UDP/TCP probe was **aborted by the user and is unexecuted**. Docker service-name resolution and verified internal OIDC HTTPS work. The failure is the external DNS path/resolver availability, reproduced before and after P5; it is not evidence of an application authorization regression.

example.com is already in the saved custom network allowlist. No supported replacement resolver or runtime repair capability is supplied to this agent. No resolver address, certificate policy or security expectation was changed. Strict acceptance needs platform-supported DNS restoration, rerunning these three exact cases, and then the relevant full suites. Until then, do not claim PASS.

## Recovery and setup failures, separately classified

Disk-full baseline/full attempts are invalidated as behavior evidence. PostgreSQL fixture writes and one legacy Grafana startup failed because Docker vfs duplicates filesystem snapshots. Completed disposable image tags and an unused PostgreSQL test-dependency cache image were removed; verified flattened dependency bases and all unrelated data were preserved. Source-mounted dependency-image overrides avoid extra copies, and executed source hashes are recorded. Namespace/rotation probes can use the verified lean base after pytest; image IDs/versions are evidence, not assumed from a tag name.

The first P5 attempt hit Compose wait's `no containers for project` after a completed bootstrap job. Exact-ID Docker wait plus exited-state/exit-code checks resolved it. A new-test import collection error was fixed; zero-case collection was never accepted. Production Nginx initially returned 500 because generated dist directories/files were 0700/0600. Same CA/config returned 200 after public assets became 0755/0644; private keys were unchanged. The driver now prepares those public permissions. A browser test initially used a full deep-link navigation that the existing SSO callback returns to home; the corrected test uses the actual Security Center navigation. Raw-body delivery was then verified with leading/trailing whitespace and Axios's trimming transform explicitly bypassed.

All final mandatory phases above were executed. Unexecuted: the aborted outside-sandbox raw-DNS diagnostic and optional controlled median/p95 performance comparison. Before/after performance figures are **not measured**; test durations across different dependency images are not latency evidence. No remaining unexpected behavioral failure is hidden as xfail/skip.

## Database, files and commands

Migration `0003_webhook_receipts` is additive, parent 0002. Composite primary key `(provider,event_id)` prevents duplicates. SHA-256 and stored JSONB response provide conflict detection/idempotent acknowledgement. Receipt reservation, simulated effect and response use one transaction. Actual catalog evidence shows eight existing foreign keys preserved; runtime SELECT/INSERT true, table UPDATE/DELETE false, UPDATE(response) true and UPDATE(provider) false. Clean upgrade/downgrade, backup/restore and historical-data adoption passed. Existing IDs and explicit external identity mappings remain intact.

Rollback must align old P4 readiness with schema head; see the reviewed backup/downgrade/redeploy procedure in the design document. Simply starting old P4 against version 0003 is not a working rollback. No production rollback or data deletion was performed.

Exact changed files: `p5-files.txt`; diff summary: `p5-diffstat.txt`. Exact runner-managed argv: `p5-commands.json`. Major executed wrappers were `python3 tests/p5/run.py --focus hardening`, `python3 tests/p5/run.py`, corrected `python3 tests/p5/run.py --focus browser`, and `python3 tests/p3/run.py`, using the documented local build/source overlays, DOCKER_CONFIG and disposable-project flags. Also executed were Git status/branch/log/fetch/base comparisons; Docker image/container/disk diagnostics and scoped cache cleanup; production npm builds; the two Node client commands; pure Settings pytest through backend/.venv; CA-verified HTTP header probes; Loki rejection queries; PostgreSQL catalog inspection; and the DNS diagnostics described above. Local override paths and startup instructions are documented in `tests/p5/README.md`; normal repository Dockerfiles remain the portable build path.

## Evidence and transfer

- `p5-focused-evidence.json`: first 75 post-fix cases/source hashes, before old xfails changed.
- `p5-candidate-evidence.json`: final integration/OIDC/host/rotation stages, retaining the original SPA setup failure.
- `p5-legacy-evidence.json`: complete separate legacy outcomes and source hashes.
- `p5-browser-evidence.json`: final 9 SDK + 8 production groups, exact whitespace delivery, zero CSP violations and query-log exclusion.
- `p5-supplemental-evidence.json`: 12 configuration cases and Node commands.
- `p5-header-evidence.json`, `p5-logging-evidence.json`: actual HTTPS status/headers and Loki 401/429 rejection evidence.
- `p5-schema-evidence.json`, `p5-preservation-evidence.json`: actual grants/schema and unchanged security paths.
- `p5-dns-diagnostic.json`, `p5-spa-permission-evidence.json`, `p5-client-runtime-evidence.json`, `p5-probe-image-evidence.json`: diagnosed environment/setup evidence.
- `p5-frontend-source-evidence.json`, `p5-oidc-evidence.json`, `p5-tls-evidence.txt`: tested frontend artifacts, public OIDC/JWKS and transport proof.
- `p5-secret-review.json`: newly staged content review, known fixture classifications and scan limitations.

Private keys, runtime passwords, bearer tokens, generated delivery files and raw credential-bearing artifacts are excluded. A pattern/manual secret review does not prove absence of every possible secret. See its actual findings and limitations. The reviewed local commit must have the approved P4 parent; bundle verification and a real local import into a repository seeded with that parent are recorded in `/workspace/cloud-api-p5-transfer.json`. [Workspace B instructions](../deployment/p5-workspace-transfer.md) explain verification, fast-forward import and a separately authorized normal push. Workspace A does not push.

Remaining limitations include single-node local quotas and reset/capacity behavior, shared proxy-peer aggregation, receipt growth/retention/backup requirements, provider-key compromise, DNS rebinding/TOCTOU beyond this non-fetching validator, external egress without a directional firewall, token exposure to successful XSS despite memory-only storage, bounded access-token validity after logout, Compose file-secret operations, standard gateway log URL hygiene and uncompleted production cutover/HA/MFA certification. Read the design for implemented versus future controls. **Stop after P5; P6/P7 are not implemented.**
