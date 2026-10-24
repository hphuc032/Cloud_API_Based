# P7 final validation and release readiness

> Follow-up, 2026-10-24: [Windows/Docker final DNS recovery](final-dns-acceptance-20261024.md)
> passed all three inherited real-DNS cases, including the active OIDC equivalents.
> Strict release acceptance remains BLOCKED by other regression/execution failures
> and unresolved dependency findings. The original P7 results below are preserved.

**Strict recommendation: BLOCKED.** P7 implements an isolated validation candidate,
not a production release. The user explicitly deferred the three inherited
real-DNS cases. Their P7 status is NOT EXECUTED, never PASS/xfail. Current dependency
and image advisory validation is also incomplete. No production deployment, main
merge, GitHub push or post-P7 feature work occurred.

Approved base/parent: `45e025703f6a193aeb5738632d436d52146f12de`, tree
`98c346dacacae3a72c0719c11b0141e4636dff14`; branch
`migration/cloud-api-security`. Initial tree was clean and remote tracking matched
this exact base. The P7 commit/tree/bundle hash and actual local import are recorded
in the external transfer manifest and completion report (no self-referential hash).
Author/committer email remains `nhpntd@gmail.com`.

## Changes and evidence boundaries

P7 adds tests/p7, this report, the security/attack assessment, reproduction/recovery/
release and demo guides, public curated evidence, README links and an ignored
artifact directory. No backend, gateway, frontend, realm, migration, network,
TLS, HMAC, RBAC or monitoring policy file changed. All 211 tracked runtime and
P0–P6 test files match approved P6 byte-for-byte: [preservation](p7-preservation.json).
No new schema migration or automatic identity binding is introduced.

P7's new 23-case suite follows actual Kong HTTPS and backend mTLS, genuine
Keycloak code+PKCE tokens, current PostgreSQL authority, selected real Loki
observations and negative-request SQL invariants. Existing suites prove additional
expiry/algorithm/token-type, session/browser, refresh, disabled/unknown identity,
role changes, ownership, concurrency, transport and privacy controls. See
[architecture/review](../security/p7-final-assessment.md),
[attack-to-control matrix](../security/p7-attack-matrix.md),
[case results](p7-case-results.json), [runtime evidence](p7-runtime-evidence.json),
[73 real event observations](p7-ingestion.json), [TLS evidence](p7-tls-evidence.txt)
and [production frontend build](p7-frontend-build.txt).

## Executed regressions

Counts below are executions per suite/run, **not additive unique cases**. Focused
P4 three cases overlap full OIDC; final recovery replaces the initial P7 failure
for acceptance but never erases it. No new skips, xfails or relaxed assertions.
Public DNS deselections are outside executed counts and documented separately.

|Run / pytest artifact|PASS|Historical expected failure|FAIL|NOT EXECUTED inside JUnit|
|---|---:|---:|---:|---:|
|initial-full / p4-focused-junit.xml|3|0|0|0|
|initial-full / p4-junit.xml|143|0|0|0|
|initial-full / p5-hardening-junit.xml|110|0|0|0|
|initial-full / p7-junit.xml|22|0|1|0|
|initial-full / p6-junit.xml|24|0|0|0|
|final-recovery / p7-junit.xml|23|0|0|0|
|legacy / p3-junit.xml|22|0|0|0|
|legacy / p2-junit.xml|83|2|0|0|
|legacy / junit.xml|106|2|0|0|

Initial full candidate `cloud-api-p7-e73da2045657`:
`2026-10-24T03:13:25.174962+00:00`–`2026-10-24T03:40:38.580537+00:00` UTC.
All original regression groups succeeded: P6 **24**, P5 **110**, full OIDC/P2/P1
**143** (two explicit DNS deferrals), host network/grants **5**, identity
persistence/isolation **3**, host TLS/mTLS **16**, real SDK/browser groups **9**,
production SPA/CSP groups **8**, signing rotation/retirement/JWKS-outage phases **6**,
collector/Loki initial/restart/backend-outage scripts **3**. All six Grafana rules
again observed pending/firing/recovery. Exact rule/query/state records are in
runtime evidence. External notification delivery is NOT EXECUTED.

The full driver returns nonzero because the initial new P7 seed expected an
unimplemented `order_created` telemetry event. The route actually logs
`http_request` and returns id/order_number/total_amount, not user_id. P7 now checks
that actual event and queries SQL for ownership. Application behavior was unchanged.
The initial seed stopped after one order; dependent restore's expected-two-orders
assertion and return verifier then failed. No recovery success was accepted there.
Initial 22 PASS / 1 failure and dependent recovery FAIL remain evidence.

Final separate recovery `cloud-api-p7-5e4f458b0e82`:
`2026-10-24T05:07:41.482886+00:00`–`2026-10-24T05:16:14.174810+00:00` UTC.
Its final 23-case suite, actual paired restore and recovered-monitoring scripts are
recorded with real exits; recovery status **PASS**. Its current-container source
guard covers the final P7 test implementation. The full run's selector was corrected
from ineffective absolute-node selection to an explicit -k expression before the
actual OIDC execution; the exact two deselected names and executed selector SHA256
are in p7-selection.json. A collection-only diagnostic is not counted as a test run.

Separate legacy `cloud-api-p3-65fb4e43e0a3`:
`2026-10-24T05:18:26.869576+00:00`–`2026-10-24T05:29:53.148977+00:00` UTC.
Actual non-DNS outcome: **245 passes +4 expected-failure executions**;
case-level counts above and runtime host results are authoritative.

|Legacy host group|PASS|FAIL/error|
|---|---:|---:|
|P1 isolation/readiness/image secrets|15|0|
|P3 identity persistence/isolation|3|0|
|P2 mTLS/rotation/proxy|16|0|
 Four legacy xfails are D01/D02 repeated locally/HTTPS, not four new
defects. P5 fixes D03–D07 remain passing. P0's immutable original seven-defect
baseline report is unchanged; no old expectation is silently rewritten.

P6 comparison: original P6 active 143 PASS + 2 DNS failures becomes 143 PASS + 2 NOT EXECUTED;
legacy 245 PASS + 4 xfail + 3 DNS failures/errors becomes the executed non-DNS matrix with
three NOT EXECUTED. This is **not DNS recovery or improved DNS acceptance**.
TLS 16, host 5/3, browser 9/8, rotation 6, P6 telemetry 24 and P5 hardening 110 remain
successful when read from their actual evidence; repeated runs are not summed.
Five scheduled DNS executions across three unique IDs are NOT EXECUTED
(two candidate plus three legacy); no focused run is added to that count.
No unexplained application/security regression is accepted.

P6's two independently proved physical-retention runs are reused unchanged, not
rerun or counted as P7 executions. [Source/probe/storage proof](p6-recovery-retention.json)
shows old object deletion, unchanged current object hash, successful sweeper count
and an independent unbounded reader. Actual production two-hour delay, natural
rollover/marker-restart and storage disaster recovery remain NOT EXECUTED.
The Node 19-assertion client contract and session-lifecycle scripts passed again. Optional stable
performance benchmarks are NOT EXECUTED: this 32GB copy-heavy vfs host reached 99%
during the first drill. No mean/median/p95/throughput/MTTD numbers are inferred
from pytest durations or a Docker stats snapshot.

## Deployment, recovery and rollback

[Reproduction guide](../deployment/p7-reproducibility.md) distinguishes fresh
lab/OIDC candidate, existing-data adoption, historical legacy and production
prerequisites. Actual commands use reviewed cloud-local dependency bases/source
mounts; current source verification and new secrets/volumes prevent cached app
code or prepopulated DBs masquerading as fresh deployment. A normal connected
registry rebuild on another host is NOT EXECUTED. Bundle import verifies clean
commit/tree reproduction, not an independent production deployment.

[Recovery plan and scope](../deployment/p7-backup-recovery.md) documents quiesced
application+identity backups streamed privately into **two fresh PostgreSQL
instances/volumes**; all public rows, constraints, table owners and critical runtime
grants are compared. Fresh PKCE exchanges on recovered IdP verify four unchanged
application UUIDs/roles, two order owners/BOLA, admin separation and no escalation.
Backend recreation and return to untouched original DBs are separate checks.
Grafana/Alloy containers are temporarily removed with their volumes retained to
bound vfs disk use; there is an explicit collection gap during this drill. Updated
narrow log mounts and actual new correlation plus four dashboards/six rule queries
are checked after recreation. No lossless-monitoring claim is made.

Both already-started drivers used the prior default-profile cleanup and left
only their own two recovery volumes/network; explicit targeted cleanup removed
them. The final source uses the recovery profile at down; a separate real Compose
profile/volume/network smoke check verifies the corrected command leaves none.
A final host-only review also moves metadata refresh after Grafana/Alloy recreation
so subsequent host probes include those peers; compilation passes. These orchestration
refinements are distinct from the unchanged executed application assertions. No global prune, unrelated stopped PostgreSQL cleanup or production
volume deletion occurred.

P7→P6 rollback is schema/grant-compatible because runtime is unchanged. Tested
return-to-original-DB routing is not a deployed historical binary rollback.
P6→P5 / P5→P4 / OIDC→legacy downgrade risks and unexecuted procedures are explicit.
Never assume Keycloak-only users have known legacy passwords or enable fallback.
Cold Loki/Grafana SQLite/Alloy positions disaster restore and encrypted off-host
backup/key-recovery/RPO/RTO exercises are NOT EXECUTED; no HA claim is made.

## Deferred DNS and security review

The initial host getent example.com returned no answers; configured resolver was
172.31.2.109. An outside-sandbox DNS request was aborted and not executed. After
the user instructed deferral, no public-DNS repair/bypass was attempted. All three
IDs are listed in [acceptance JSON](p7-acceptance.json): P1 backend namespace
getaddrinfo(example.com,443), P2 staff/admin HTTPS URL validation of example.com/test.
Actual Docker service-name DNS and verified internal HTTPS are exercised by the
passing application/provider tests; they do not certify external DNS.
No hardcoded public answer/resolver, hosts substitution, verification bypass or
mocked real-DNS PASS is used. After genuine supported recovery, run the exact
three cases first, then full unfiltered `tests/p7/run.py` and `tests/p3/run.py`.

[Dependency/security review](p7-security-review.json) records installed Python and
npm versions, image IDs, inventory, offline npm audit exit0 and OSV CONNECT403.
The outside-sandbox advisory retry was aborted. No current advisory or OS-image
scan completed; the empty offline result must not be called a clean scan. Older
inherited library/Keycloak/Kong/Loki/Grafana versions need supported connected,
version-aware advisory/reachability review before release; no automatic upgrade,
unverified CVE/fixed-version claim or speculative test suppression was made.

## Strict A–R matrix

|ID|Area|Status|Actual evidence and limits|
|---|---|---|---|
|A|Functional end-to-end|PASS|Real Keycloak tokens, Kong HTTPS, backend mTLS, user/product/order APIs; both browser groups|
|B|Authentication|PASS|Real S256, state/nonce, refresh/logout/expired session, retired local issuance, signing rotation/JWKS outage|
|C|Authorization / BOLA|PASS|Current PostgreSQL role/is_active; own/other order and administration; no email linking|
|D|Webhook integrity / replay|PASS|HMAC forgery/retry/conflict, eight concurrent local deliveries, real receipt/transaction rollback|
|E|SSRF|BLOCKED|Nonpublic/mapped/mixed-answer denials pass; actual allowed public DNS success deferred|
|F|Input validation|PASS|Null/invalid price/role/UUID/JSON and SQL-shaped IDs; no partial mutation|
|G|HTTPS / mTLS|PASS|22 socket/certificate cases inside candidate suite plus 16 actual host checks and browser CA/SAN|
|H|Database least privilege|PASS|18 candidate privilege cases, five host isolation/grant checks, identity isolation, restored grants|
|I|Audit logging|PASS|Atomic business/audit commit/rollback; runtime INSERT-only; correlation/privacy tests|
|J|Alloy / Loki|PASS|Real events queried; restart preservation; refreshed narrow mounts after backend recreation|
|K|Grafana dashboard queries|PASS|Four provisioned dashboards; all target expressions executed; recovered Grafana verified|
|L|Grafana alerting|PASS|Six unchanged rules real pending/firing/recovery. External notifications NOT EXECUTED|
|M|Deployment reproducibility|PASS|Fresh full/focused projects, secrets, volumes, migrations, realm, source guard, verified dependency bases. Fresh Internet registry rebuild NOT EXECUTED|
|N|Backup / restore|PASS|Paired quiesced DB archives -> two fresh PostgreSQL instances; rows/owners/constraints/grants and recovered real PKCE/API assertions. Cold Loki/Grafana/positions disaster restore NOT EXECUTED|
|O|Rollback preparedness|PASS|Documented P7-to-P6 schema-compatible plan; tested return to original DBs. Historical release deployment/security downgrade NOT EXECUTED|
|P|DNS integration|BLOCKED|Three inherited real-DNS IDs NOT EXECUTED by explicit user instruction; no bypass|
|Q|Security / dependencies|BLOCKED|Runtime/code/secret review recorded; OSV proxy403, retry aborted, no current scanner/image feed; offline npm audit0 is not certification|
|R|Documentation / demonstration|PASS|Tested lab entry points, case traceability, attack matrix, scoped recovery and evidence-based demo guide|

[Machine-readable matrix](p7-acceptance.json) uses explicit gate labels.
Mandatory E/P and Q are BLOCKED; this cannot be an unconditional release PASS.
See [security limitations](../security/p7-final-assessment.md) for fixed-window
quotas, token revocation/XSS, SQL/egress boundaries, simulated webhook effects,
audit/host trust, Loki spoofing/loss and production PKI/operations risks.

## Commands and deliverables

[Runner argv](p7-commands.json) records actual commands and cleanup; [source/build
and environment review](p7-security-review.json) and the
[zero-test legacy startup failure](p7-legacy-startup-failure.json) record supporting diagnostics.
Top-level commands executed: `git status/log/rev-parse/merge-base`, Docker
version/Compose/ps/images/inspect/stats/systemdf and disk checks,
`python tests/p7/run.py --defer-public-dns`,
`python tests/p7/run.py --focus recovery --defer-public-dns`,
`python tests/p7/legacy.py --defer-public-dns`, two Node client/session scripts,
Python source compilation, a rejected stale legacy source mount (zero cases),
its corrected fresh source-mounted rerun, public evidence curation, `git diff --check`, secret
review and local commit/bundle/real import checks. The initial public DNS command,
OSV request and offline audit are diagnostic attempts, not passing security scans.

[Changed-file inventory](p7-files.txt), [diff summary](p7-diffstat.txt),
[secret review](p7-secret-review.json), [demo](../demo/p7-security-demo.md),
[release/Workspace B transfer](../deployment/p7-release-checklist.md) complete the
candidate. Public evidence excludes private dumps/role verifiers, passwords,
access/refresh tokens, codes, private keys and raw container inspection. Pattern
review plus manual curation has limitations and is not universal absence proof.
Only local commits and a verified bundle/import are performed. **STOP after P7.**
