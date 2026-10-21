# P6 security observability — acceptance report

**Recommendation: BLOCKED.** Structured telemetry, transactional audit, Alloy ingestion, dashboards and local Grafana rule evaluation are implemented and tested. Mandatory physical-retention validation failed, and the three inherited real-DNS cases remain unresolved. This is a reviewable P6 candidate, not an accepted production release. No P7 work or GitHub push is performed.

Approved parent: `9ebca60bff2947e26b2a91ef0273118d21fd6c05`. Initial branch, local HEAD, origin branch and committed tree matched exactly; the working tree was clean. Prior commits were not reset, rebased, amended or rewritten. Exact resulting commit/tree and verified bundle SHA256 are recorded in the external transfer manifest to avoid a self-referential commit hash in this file.

## Architecture, event coverage and audit

See [actual architecture and threat matrix](../monitoring/p6-architecture.md), [event/source/severity/privacy matrix](../monitoring/security-events.md), [detection rules](../monitoring/detection-rules.md), [operator response](../monitoring/alert-response.md) and [deployment/rollback](../deployment/p6-observability.md).

Kong replaces caller request IDs at the controlled boundary, forwards a generated canonical UUIDv4 over the existing enrolled mTLS connection and echoes it on gateway-only and upstream responses. FastAPI validates ID shape, uses normalized framework routes and emits allowlisted JSON. Tests prove forged IDs are replaced, gateway-only401 never appears as an application request, successful gateway/API events correlate, and IDs do not become Loki labels. Stored labels are limited to project/service.

Coverage includes JWT rejection, unmapped/disabled identities as a combined non-enumerating category, RBAC and ownership denials, gateway429, webhook rejection/authenticated retry/conflict, SSRF destination-policy denial,422 validation, Keycloak login failure and controlled upstream502. A customer forbidden from entering the SSRF endpoint is RBAC denied, not an SSRF destination event. An upstream webhook401 is not mislabeled a gateway JWT rejection.

The existing audit table/schema is reused. User administration, product create/update/deactivate and order status changes write actor/resource UUIDs, action, correlation UUID and schema version in the business transaction. No payload, password, email, shipping data, raw header or before/after personal values are copied. Actual SQL tests verify records, commit/rollback and INSERT-only runtime privileges. SELECT/UPDATE/DELETE remain denied; only sequence USAGE is added. Inline INSERT avoids RETURNING/read grants. Owners can modify records and a compromised writer can append false records; this is not immutable or tamper-proof storage.

## Alloy, storage, dashboards and alerts

Alloy1.14.1 is digest-pinned and replaces Promtail only in the P6 candidate. Historical Promtail configuration is retained unchanged and its ingestion path is independently tested by the legacy suite. Alloy receives reviewed project-only container directories read-only, no Docker socket, no capabilities and a read-only root. Its fresh nocopy positions volume and readable empty mount root avoid dependence on DAC override. Runtime source hashes cover backend, mounted plugin, Alloy and Loki configuration.

Kong and FastAPI exclude headers/bodies/query strings before Docker persistence. SPA and identity-edge access logs omit query parameters; raw proxy error output is suppressed. A small tracked OSS log-phase plugin reads a bounded128KiB OpenResty memory ring and exports only four constant upstream TLS verification reasons. Those worker events explicitly remain unattributed; correlated HTTP502 observations are separate. Keycloak's failed-login event becomes constant JSON before Loki, and other Keycloak lines are dropped. Host Keycloak logs can retain identity metadata under bounded Docker rotation; host privacy/access controls still matter. Settings error messages and repr exclude credential inputs; Uvicorn exception text and SQL statement/detail logging are suppressed.

Loki uses a fresh P6 volume, filesystem storage, v11/24-hour boltdb index, explicit filesystem shared_store, single replica and an in-memory ring. Configured target retention is168hours with a2hour deletion delay. Ingestion is2MiB/s with4MiB burst; queries cap1000series/5000entries. Docker sources rotate at10MiB ×3. These are not a hard Loki disk quota or HA/backup guarantees.

Four automatically provisioned dashboards use stable datasource/dashboard UIDs and real LogQL. All provisioned panel queries are exercised; Grafana visual rendering is not separately browser-certified. Six rules cover JWT rejection, webhook rejection/conflict, ownership denial, SSRF denial,429 and upstream errors. Actual Grafana evaluation starts inactive, enters pending/firing after real gateway traffic and recovers inactive. All rules are provisioned and query successfully; only the JWT rule has a dedicated end-to-end threshold/firing/recovery experiment. No external notification channel or delivery is configured/tested. Missing-data/error states are configured, not exhaustively fault-injected. There is no fabricated live availability, storage metric or MTTD/MTTR.

## Authoritative regression matrix

Counts are executions within each phase, not unique vulnerabilities. Repeated diagnostic/focused runs are not added as new unique cases. Browser groups and lifecycle scripts are separate from pytest counts. Final recovery results are recorded in `p6-final_recovery-evidence.json`; any nonzero command remains visible.

| Phase | Passed | Expected failure | DNS fail/error | Other unresolved failure |
| --- | ---: | ---: | ---: | ---: |
| Final P6 telemetry/audit/redaction/engine pytest |23|0|0|0|
| Final P5 hardening/configuration pytest |110|0|0|0|
| Final active OIDC/P2/P1 pytest |143|0|2|0|
| Final active network/privilege/Alloy host |5|0|0|0|
| Active P3 identity persistence/isolation host |3|0|0|0|
| Final P2 TLS host |16|0|0|0|
| Actual sanitized TLS reason ingestion script |1|0|0|0|
| Final collector/Loki restart, duplicate observation and backend outage scripts |3|0|0|0|
| P4 SDK/browser lifecycle/state/nonce/outage |9|0|0|0|
| Production SPA/CSP/Security Center browser groups |8|0|0|0|
| Key rotation/retirement/JWKS-outage phases |6|0|0|0|
| Separate legacy P0/P1 pytest |106|2|0|0|
| Separate legacy P2 HTTPS/business pytest |83|2|2|0|
| Separate legacy P3 OIDC/mapping pytest |22|0|0|0|
| Separate legacy P1 host |15|0|1error|0|
| Separate legacy P3 persistence host |3|0|0|0|
| Separate legacy P2 TLS host |16|0|0|0|
| Clean isolated physical-retention experiment |0|0|0|1|

Legacy totals: **245pass/4expected failures/3DNS failures/errors across252executions**, matching P5. The four xfails represent only two unique legacy JWT defects D01/D02, each exercised locally and over HTTPS. P5's five fixes D03–D07 remain passing. Active OIDC has no baseline xfails. P0/P1 emitted two existing deprecation warnings.

Also passed: `node tests/p3/test_client.mjs` (19 assertions, not19pytest cases), `node tests/p4/test_session.mjs`, production frontend build, isolated logger assertions, original P4 focused3case subset, Python AST checks and `git diff --check`. Source comparison proves auth dependency decisions are identical after removing telemetry-only marks, and SSRF validator helpers are unchanged. Final API suites additionally exercise the Settings error/repr privacy changes. Browser/identity/rotation evidence comes from the earlier full run with identical authentication, business and TLS decisions, before the final transport-log relay and error-format refinements; that scope is not hidden.

### DNS, separately retained

Three distinct required IDs remain visible:

1. P1 host `test_public_dns_for_current_ssrf_validation`: backend-namespace `socket.getaddrinfo('example.com',443)` errors with gaierror errno-3; subprocess exits1.
2. P2 `test_https_ssrf_uses_real_dns_and_preserves_roles[staff-200]`: expected200, actual400 `Unable to resolve hostname`.
3. P2 same `[admin-200]`: same result.

The two P2 IDs run in active and legacy matrices, giving five DNS fail/error executions across three unique cases. Earlier repeated runs are recorded separately. Agent resolver remains172.31.2.109; example.com and pypi.org fail host resolution. Internal Compose names, OIDC HTTPS and mTLS operate. No resolver substitution, DNS mock, skip, xfail conversion or TLS bypass is used. A new outside-sandbox diagnostic request was aborted before execution and is explicitly unexecuted. Platform-supported DNS repair and real reruns remain required for P3–P6 acceptance.

### Retention — mandatory unresolved gate

`python3 tests/p6/retention.py` runs only on a random isolated Compose project/volume. It admits two synthetic samples (eight days old/current), keeps the actual168hour policy and accelerates compaction/flush/delete delay; this direct storage probe is not security-event collection evidence. It requires the expired sample to disappear, the current sample to remain and a successful physical-deletion metric. The production2hour delay is not wall-clock tested.

The clean480second experiment **failed**: both samples remained queryable and no successful physical-deletion metric was observed. No blanket retention PASS is claimed. Initial baseline visibility assumptions were corrected after observing shipper/flush visibility; the physical-deletion condition remained mandatory. An empty shipper shared_store was found and made explicit, but that change did not establish deletion and is not asserted as the sole root cause. Shipper/compactor timing/storage behavior still needs independent diagnosis. Early runs affected by concurrent disk pressure do not establish production retention behavior. The clean failure remains a P6 validation blocker, not a DNS failure or expected failure.

## Intermediate failures and recovery

Intermediate issues are retained rather than relabeled baseline defects: initial Compose dollar escaping and incorrect new fixture/route names; nested mounts under a read-only parent; Grafana public-directory permissions; unsupported UUID require in the serverless sandbox; a Loki-incompatible empty regex; Alloy match selector runtime syntax; vfs DiskFull; positions ownership and empty mount-root traversal after capability removal. Final IDs use Nginx-generated random bytes, not untrusted headers. A focused run passed16P6/110P5 before the final expanded coverage.

The first full run had7missing-ingestion failures caused by collector startup permissions;10other P6 cases passed after diagnosis. Its original P2 host suite had12pass/4fail because suppressed raw logs removed the four TLS-reason substrings, even though all four invalid peers still produced502. The new constant-reason relay preserves those original assertions; no P2 assertion or certificate check was weakened. A later concurrent full-stack startup exceeded the32GiB vfs host and failed P6 Loki initialization; zero tests from that startup are accepted. Final acceptance runs are serialized and use reviewed dependency exports/imports and source mounts. No production volumes or the unrelated stopped PostgreSQL container/data were modified.

## Evidence, commands, files and transfer

- `p6-final_recovery-evidence.json`: final per-case outcomes, host results and actual rule states.
- `p6-initial_full-evidence.json`, `p6-legacy-evidence.json`, `p6-focused-evidence.json`: full prior/focused/legacy outcomes and scope.
- `p6-ingestion-evidence.json`, `p6-alert-evaluation.json`, `p6-lifecycle-evidence.json`, `p6-transport-ingestion.json`: real stored event samples, Grafana engine state transitions and actual restart/outage/transport observations.
- `p6-retention-clean-evidence.json` and earlier retention evidence: failing storage experiments, including accepted samples and counters. They are not erased or called skipped.
- `p6-runtime-source-evidence.json`, `p6-policy-comparison.json`, `p6-preservation.json`, `p6-network-logging-evidence.json`, `p6-local-images.json`: runtime hashes, unchanged policy/TLS artifacts, networks, grants/logging settings and dependency provenance.
- `p6-preflight.json`, `p6-supplemental.json`, `p6-unit-evidence.json`, `p6-resource-snapshot.json`: preflight/DNS, client/build checks and one actual resource snapshot.
- `p6-files.txt`, `p6-diffstat.txt`, `p6-secret-review.json`: complete file inventory, diff summary and reviewed staged-secret scan.

`p6-commands.json` contains exact runner-managed argv. Executed wrappers: `python3 tests/p6/run.py --focus hardening`, `python3 tests/p6/run.py`, final `python3 tests/p6/run.py --focus telemetry`, separate `python3 tests/p3/run.py` and repeated `python3 tests/p6/retention.py`. Cloud-local P4/P5/P3 dependency/source overlays and original stop signals are recorded; standard tracked Dockerfiles remain the portable path. Additional diagnostics included Git status/branch/HEAD/remotes/fetch/tree comparison; Docker version/inspect/images/logs/stats/systemdf; disk inspection and scoped unused dependency-cache cleanup; public runtime SHA256 checks; actual PostgreSQL logging/grant queries; source-policy AST comparisons; source/config validation; DNS resolution; Node/build commands; and final secret/bundle/import checks. Read-only exploration is summarized rather than represented as runner-managed commands.

There is no new Alembic revision. P6 reuses the existing audit schema and explicitly re-applies reviewed grants. Rollback requires traffic drain, preservation of P6 observability data, reviewed P5 OIDC deployment/configuration and reapplying P5 runtime grants; it must not silently retain audit writer privileges or switch to legacy token issuance. Details and Workspace B-only import/fast-forward commands are in the deployment document. The external manifest contains exact commit, parent, tree, bundle hash and real local-import verification. Workspace A does not push.

## Remaining limits / unexecuted checks

Mandatory blockers are DNS and physical-retention validation. Other unexecuted checks: all five non-JWT alert threshold/firing/recovery experiments, external delivery, grouping/silences/mutes, exhaustive missing-data fault injection, forced source rotation/long pipeline outage/positions loss, Loki/Grafana backup restore and migration of existing production volumes. Grafana UI rendering is not separately browser-tested. Before/after latency, median/p95 overhead, log-growth and alert-delay benchmarks are unmeasured. The Docker resource snapshot is one sample, not a benchmark or MTTD/MTTR claim.

Old Loki2.9.8/Grafana10.4.2 are retained for bounded compatibility tests and require support/vulnerability review or a validated upgrade before production; version pins are not support certification. Single-node filesystem storage is not HA and has no hard disk quota. Loki has no built-in auth here; private-network peers can forge telemetry. Remote Grafana management requires a verified HTTPS/authenticated boundary; loopback/internal HTTP is not an Internet deployment. Alloy can read selected Docker metadata and rootless/user-namespace layouts are not validated. Retry exhaustion, full disks and rotated source files can lose logs. Audit owners/host admins can tamper; raw host Keycloak identity metadata remains a privacy consideration. Neither privacy compliance nor operational incident-response effectiveness is claimed.

**Stop after P6 candidate testing, local commit and verified bundle. P6 acceptance is BLOCKED; do not begin P7.**
