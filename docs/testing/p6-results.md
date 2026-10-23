# P6 security observability — acceptance recovery report

**Recommendation: BLOCKED — external DNS.** Physical retention is independently
proved on repeated fresh volumes. All six provisioned alert rules have real pending/firing/recovery evidence. The three inherited real-DNS
regression IDs remain environmental blockers; they are not skipped, mocked or
converted to expected failures. No P7, production-volume migration or GitHub push
was performed.

Recovery starts from P6 `3d6f2ff3b2d8fe432df000b6c4beaebec744f291`, on
`migration/cloud-api-security`, with approved P5 parent
`9ebca60bff2947e26b2a91ef0273118d21fd6c05`. Previous history is unchanged. The new
local recovery commit, tree, verified bundle SHA256 and real import verification
are recorded in the external transfer manifest to avoid a self-referential hash.

## Retention root cause and changes

See [full version-compatible diagnosis](p6-retention-recovery.md),
[official source URLs/SHA256](p6-recovery-retention-sources.json),
[actual image provenance](p6-recovery-image-provenance.json) and
[failed/successful experiments](p6-recovery-retention.json).

Loki2.9.8/revision94e00299ec supports this filesystem/v11 boltdb-shipper/24h index
retention design. The original probe flushed chunks but waited only480seconds:
its newly written local index was still in a15minute write-time shard plus a
one-minute safety buffer. Compactor cycles could not process an index that had
not shipped. Explicit shared_store alignment alone could not fix that lifecycle.
A supported graceful stop forces index handover; restart then produces real
retention markers and successful chunk deletion. No upgrade, timestamp/shard
manipulation, reduced168h policy or direct delete request was needed.

Query/cache visibility was a second independent issue. Local writer index/chunk
caches could serve the old record after its shared object disappeared; an
accelerated diagnostic single-binary query eventually converged after~462s.
Production now explicitly sets `limits_config.max_query_lookback:168h`, matching
the unchanged physical policy and preventing cached expired records from being
returned. Physical retention remains168h, compaction1m, deletion delay2h.

The probe now uses a separate read-only querier with its own temporary cache and
**max_query_lookback:0s**. Its query cannot pass merely because of the production
lookback filter. Exact old/current object keys are decoded and matched to sample
event timestamps; size/SHA256, actual successful-deletion histogram count,
independent query results and writer queries are all required. The reader has no
host port, a read-only root/object mount, dropped capabilities and temporary cache.

Two authoritative final-source repeats:

| Project suffix | Unbounded reader before | After | Writer after | Physical proof | Observation loop |
| --- | --- | --- | --- | --- | ---: |
| `8fd1584c3c` | old1/current1 | old0/current1 | old0/current1 | Old object absent; current SHA256 unchanged; success count1 |65.27s|
| `7c3b4bd0c3` | old1/current1 | old0/current1 | old0/current1 | Old object absent; current SHA256 unchanged; success count1 |70.39s|

Both exited0 and cleaned up their own volumes/networks with exit0. Durations
exclude startup, seed and graceful shutdown. Earlier successes/failed experiments
remain evidence, not extra unique acceptance cases. The original clean failure
is preserved in [p6-retention-clean-evidence.json](p6-retention-clean-evidence.json).

Only the disposable probe accelerates flush/compaction/index cache/resync/delete
delay and admits old samples. The sweeper's own one-minute cycle is unchanged.
The actual **production two-hour deletion delay has not been wall-clock tested**;
natural shard rollover, marker recovery after a compactor restart, production
volume migration and backup/restore remain unverified. The experiment proves the
mechanism, not an exact production deletion SLA or a hard disk quota.

Private RPC also encountered an independent recovery-environment proxy failure:
The default Docker client config injected proxy172.31.2.109:8080 with loopback-only NO_PROXY; Go gRPC and Python HTTP attempted that unreachable external proxy from the isolated storage network. Sanitized evidence is in [proxy diagnostics](p6-recovery-proxy-diagnostics.json). The
P6 Loki service clears proxy variables/sets NO_PROXY, and the private probe uses
`ProxyHandler({})`. This does not replace DNS, relax TLS or alter application
security. The intermediate unsupported query-path/configuration/reader-startup
failures are retained with real nonzero exits.

## Critical detection validation

All six provisioned rules passed actual engine firing/recovery. The five
previously unexecuted rule experiments now have the following exact query values:

| Additional rule | Real count | Threshold | Observed state sequence |
| --- | ---: | ---: | --- |
| Webhook rejection/conflict |9|>3|inactive -> pending -> firing -> inactive|
| Ownership/BOLA denial |8|>3|inactive -> pending -> firing -> inactive|
| SSRF denial |8|>3|inactive -> pending -> firing -> inactive|
| Gateway rate-limit429 |12|>5|inactive -> pending -> firing -> inactive|
| Controlled upstream failure |8|>3|inactive -> pending -> firing -> inactive|

The existing JWT spike experiment also passed again. See
[p6-recovery-alerts.json](p6-recovery-alerts.json) for exact UTC observation/engine
evaluation times and query values, and [final raw engine evidence](p6-recovery-final.json)
for the snapshots. Two-second sampling can observe pending after it began; sampled
elapsed time is not a modified pending policy or an MTTD/MTTR benchmark.

The source rules remain unchanged: actual60s LogQL windows,10s evaluation group,
30s pending. Real gateway/application events are generated with existing
JWT/mTLS, PostgreSQL role/ownership and HMAC policies. Missing/forged signatures,
authenticated receipt conflicts, ownership denial, SSRF policy denial, real429
and a stopped-backend upstream failure are used; no synthetic security series or
direct Loki push substitutes for the collector path. Each experiment begins at
inactive, checks real ingested events and query values above the provisioned
threshold, observes pending/firing and returns inactive. Exact UTC evaluation
samples, query strings/values and request IDs are retained.

**External notification delivery is not configured or tested.** These are actual
local Grafana engine results, not proof of email/webhook delivery, grouping,
silencing, missing-data fault handling or incident-response effectiveness.

## Authoritative regression matrix

Counts are executions within a phase. Repeated focused reruns, browser groups and
scripts must not be summed as unique vulnerabilities. Initial failed experiments
remain visible and separate from final outcomes.

| Active/candidate phase | Pass | Expected failure | DNS failure | Other unresolved failure |
| --- | ---: | ---: | ---: | ---: |
| Final P6 telemetry/audit/privacy/alert pytest |24|0|0|0|
| P5 hardening (full run; final repeat) |110;110|0|0|0|
| Full active OIDC/P2/P1 pytest |143|0|2|0|
| Full active network/privilege/Alloy host |5|0|0|0|
| Full active P3 identity persistence/isolation host |3|0|0|0|
| P2 TLS/mTLS host (full; final transport repeat) |16;16|0|0|0|
| Final transport network/privilege/Alloy repeat |5|0|0|0|
| Final actual four sanitized TLS-reason ingestion script |1|0|0|0|
| SDK/browser lifecycle/state/nonce/outage groups |9|0|0|0|
| Production SPA/CSP/Security Center browser groups |8|0|0|0|
| Rotation/retirement/JWKS-outage phases |6|0|0|0|
| Collector/Loki restart + duplicate observation + controlled outage (full; final) |3;3|0|0|0|
| Final-source independent physical-retention repeats |2|0|0|0|

The full P4 focused3case subset also passed; it overlaps the full active suite.
The initial full run's P6 phase had23pass/1new-test failure; the final24pass replaces
that assertion failure for acceptance, while preserving its original evidence.
The full run precedes the final logical-lookback/probe refinements; the final
P6/P5 rerun exercises the final Loki configuration and corrected alert test.
Authentication, business policy, TLS, realm, Alloy and alert-rule sources are
identical across those runs. The final transport supplement reran all16TLS/mTLS and5network/privilege checks
with final Loki configuration, then independently queried all four real sanitized
TLS verification reasons in Loki. It preserves every original assertion and
supplements the full regression; it does not replace any DNS-dependent case.

| Separate legacy phase | Pass | Expected failure | DNS fail/error | Other unresolved failure |
| --- | ---: | ---: | ---: | ---: |
| P0/P1 pytest |106|2|0|0|
| P2 HTTPS/business pytest |83|2|2|0|
| P3 OIDC/mapping pytest |22|0|0|0|
| P1 host |15|0|1error|0|
| P3 persistence/isolation host |3|0|0|0|
| P2 TLS/mTLS host |16|0|0|0|

Legacy total: **245pass / 4expected failures / 3DNS fail/errors across252executions**,
matching approved P5 and the original P6 regression. Two existing deprecation
warnings remain. Both active and legacy retain nonzero DNS failure results;
they are not counted as passed or expected failures.

Four legacy expected failures represent only two unique historical JWT defects,
D01/D02, exercised locally and over HTTPS. P5 fixes D03–D07 remain passing. Active
OIDC has no baseline xfails. No new expected failure or skip was introduced.
The initial new alert test incorrectly expected400 for a literal-IP SSRF deny;
the unchanged application/previous tests require403. That new assertion was fixed
to exact403, and the whole P6 suite was rerun. Its initial23pass/1failure is
preserved in [initial P6 evidence](p6-recovery-initial-p6.json), not relabeled as a
baseline defect. Earlier full source-guard/build-environment failures accepted
zero tests and are separately documented.

Also rerun: `node tests/p3/test_client.mjs` (19 assertions, not19pytest cases),
`node tests/p4/test_session.mjs`, new Python source compilation and
`git diff --check`. Browser/state/nonce, production frontend build/CSP and actual
rotation/retirement/JWKS outage are recorded in the full run. The final P6/P5
rerun uses the final Loki configuration and current mounted-source hash guard.

## DNS — unresolved environmental acceptance gate

| Required ID | Actual result |
| --- | --- |
| P1 host `test_public_dns_for_current_ssrf_validation` | Backend `socket.getaddrinfo('example.com',443)` raises gaierror errno-3; subprocess1 |
| P2 `test_https_ssrf_uses_real_dns_and_preserves_roles[staff-200]` | Expected200, actual400: `Unable to resolve hostname` |
| P2 same `[admin-200]` | Expected200, actual400: `Unable to resolve hostname` |

P2 invokes the existing SSRF resolver `getaddrinfo('example.com',None)` for
`https://example.com/test`. These two IDs appear in both active and legacy runs:
five fail/error executions across three unique IDs. Host example.com/pypi.org
queries also fail. An actual outside-sandbox `getent ahosts example.com` exited2
with no result. Docker127.0.0.11 forwards to host172.31.2.109; its configuration
shows no resolver override. Internal postgres/kong names resolve and verified
HTTPS/mTLS/OIDC work. See [DNS commands and exact errors](p6-recovery-dns.json).

The shared external resolver/forwarding path remains unavailable across the
Agent and backend namespace, consistent with the inherited P1/P2/P3/P5/P6
failures. Application security sources are unchanged; no application regression
explains this cross-environment failure. The precise platform resolver/egress
fault cannot be diagnosed from these results alone. The environment operator must
restore a supported external DNS forwarding/resolver path, then rerun these three
IDs and the full suite. HTTP proxy connectivity is not a substitute for raw DNS.
No public resolver/address hardcode, /etc/hosts substitution, DNS mock, weakened
SSRF expectation, certificate bypass or expected-failure conversion was used.
Fixing retention did not fix DNS, so P6 cannot be accepted.

## Preserved architecture and release integrity

The [architecture](../monitoring/p6-architecture.md),
[event/privacy matrix](../monitoring/security-events.md),
[detection rules](../monitoring/detection-rules.md),
[response procedures](../monitoring/alert-response.md) and
[deployment/rollback](../deployment/p6-observability.md) remain the operational
references. [Source preservation evidence](p6-recovery-preservation.json) proves
backend, gateway, frontend, P2/P4/P5 policy and Keycloak source/configuration are
unchanged from P6. Runtime network/privilege, persistence and TLS checks are
recorded separately in the regression evidence.

P1 private networks/database privileges; P2 HTTPS/mTLS/enrollment; P3 separate
identity PostgreSQL and explicit identity mappings; P4 issuer/audience/JWKS,
PostgreSQL RBAC/is_active/ownership; P5 webhook receipts/HMAC/SSRF/input/gateway/CSP;
and P6 structured logs/privacy/correlation/Alloy/audit remain intact. No new
Alembic revision or application migration is introduced. No authentication
fallback, role assignment from token claims, account auto-linking or cutover is
added. The unrelated stopped PostgreSQL container/data are untouched.

Changes are limited to Loki logical lookback/private proxy environment, retention
and alert test infrastructure, diagnostic source-mismatch reporting and public
documentation/evidence. Prior commits are not amended/reset/rebased. The new
recovery commit uses `nhpntd@gmail.com`; changed staged/committed files undergo
secret review. The bundle includes P6 and its recovery on approved P5, is verified
and actually imported into an isolated bare repository with commit/tree/ancestry
checks. Workspace A does not push.

## Commands, evidence and remaining limits

Actual runner-managed argv and return codes are in the full/final/legacy recovery
JSON evidence. The executed release commands are:

```sh
python3 tests/p6/run.py
python3 tests/p6/run.py --focus hardening
python3 tests/p6/run.py --focus transport
python3 tests/p3/run.py
python3 tests/p6/retention.py  # repeated fresh projects; failures also preserved
node tests/p3/test_client.mjs
node tests/p4/test_session.mjs
```

Cloud-local wrappers set writable DOCKER_CONFIG, reviewed P4/P3 build and source
overlays, verified test/probe base images and the existing reusable probe worker.
Standard tracked Dockerfiles remain the portable path. Public dependency image
IDs/digests are recorded. Additional commands included Git status/diff/ancestry,
Docker version/images/inspect/logs/systemdf, disk checks, official v2.9.8 source
fetches, host/outside-sandbox/backend DNS diagnostics, source-policy comparison,
Python compilation, secret review and bundle/real-import verification. No global
Docker volume prune or unrelated PostgreSQL cleanup was performed.

- [Full active run](p6-recovery-full.json): per-case results, command argv, browser/rotation/network/TLS evidence.
- [Final P6/P5 recovery](p6-recovery-final.json): final24/110passes, source hashes, lifecycle and all rule-state snapshots.
- [Final transport and real four-reason ingestion](p6-recovery-transport.json): final-config16TLS/5network passes and actual Alloy/Loki samples.
- [Separate legacy run](p6-recovery-legacy.json): per-case pass/xfail/DNS results and host checks.
- [Retention runs/config/log excerpts/object hashes/metrics](p6-recovery-retention.json), [detailed root cause](p6-retention-recovery.md), [official sources](p6-recovery-retention-sources.json).
- [Alert summary](p6-recovery-alerts.json), [DNS diagnostics](p6-recovery-dns.json), [sanitized proxy diagnosis](p6-recovery-proxy-diagnostics.json).
- [Initial new-test failure](p6-recovery-initial-p6.json), [zero-test startup failures](p6-recovery-startup-failures.json), [supplemental client checks](p6-recovery-supplemental.json).
- [Source preservation](p6-recovery-preservation.json), [image provenance](p6-recovery-image-provenance.json), [changed files](p6-recovery-files.txt), [secret review](p6-recovery-secret-review.json).

The external retention evidence archive contains101verified raw synthetic-storage
files/console logs, including failed runs; its SHA256 and member hashes are in the
external evidence manifest. The new Git transfer manifest contains the recovery
commit/tree, approved base, verified bundle hash and real bare-repository import
checks. Existing P6 evidence and its original commit remain unchanged.

Remaining limits: platform DNS; production two-hour retention timing/natural
rollover/marker restart/backup restore; external alert delivery and
silence/grouping/error/missing-data fault injection; forced source rotation,
long collector outage/positions loss; production volume migration; standalone
Grafana UI rendering; before/after latency/p95/overhead/log-growth/MTTD/MTTR
benchmarks. A prior Docker stats sample is not a benchmark. Logical lookback is
not physical-deletion proof, and delayed physical retention is not a hard disk
quota.

Loki2.9.8/Grafana10.4.2 still require support/vulnerability review or validated
upgrade before production. Filesystem/single-node storage is not HA; Loki's
private-network peers can forge telemetry. Grafana remote management needs a
verified HTTPS/authenticated boundary. Retry exhaustion, full disks and rotated
files can lose logs. Audit owners/host admins can tamper, a compromised runtime
can append false records, and raw host Keycloak metadata remains a privacy risk.
No WORM, privacy-compliance, operational response or production readiness claim
is made.

**STOP after P6 acceptance recovery. Acceptance remains BLOCKED. Do not begin P7.**
