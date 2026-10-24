# Final DNS acceptance recovery — Windows / Docker Desktop

**DNS gate: PASS. Overall release acceptance: BLOCKED.** All three inherited
real-DNS cases passed unchanged on the approved source. This does not erase new
failures encountered by the unfiltered regression drivers or unresolved dependency
advisories. No application, authentication, gateway policy, TLS, network, migration
or security-test assertion was changed by this recovery.

Source: `90117e623bfa2e18d701e1f283b2b617b9a50270`, branch
`migration/cloud-api-security`. Tracked files initially matched this commit.
Existing untracked documents/attack-scenario directories were preserved. This is
a follow-up evidence record; P3–P7 historical reports and their previous failures
remain historical evidence. Only a new documentation/evidence commit is intended;
no push, reset, rebase, amend, main merge or production deployment is performed.

## Environment and execution boundary

Windows 11 Home Single Language, build 26300; Windows Python 3.14.2, Node 24.14.0,
npm 11.9.0. Docker Desktop was installed but stopped; `docker desktop start
--detach` started its Linux engine. Docker Engine/client 29.4.3, Compose 5.1.3;
engine allocation 20 CPUs and 8,171,724,800 bytes RAM. Existing `nginx`, `backend`
and `Duck-nettool` containers were not used as lab services.

The documented runners require Linux paths, NSS/certutil and Chromium. They were
executed through Docker Desktop's Ubuntu WSL integration, using Python 3.12.3,
an isolated cryptography 46.0.5 / PyYAML 6.0.3 tooling venv, Node 18.19.1 and
npm 9.2.0. Test containers use Python 3.11.2; the rebuilt application uses Python
3.11.17. Browser tooling was installed through the locked Playwright 1.58.2
package in the disposable source copy; Chromium's exact version is in diagnostics.
These are host test dependencies, not application dependency upgrades.

Observed service versions: Keycloak 26.2.5, Kong 3.8.0, PostgreSQL 16.15,
Loki 2.9.8, Grafana 10.4.2, Alloy 1.14.1 and nginx 1.27.5. The test browser is
Chrome for Testing 145.0.7632.6. Original requirement/lock/image-version pins were
not edited; normal image rebuilds resolve permitted transitive dependencies and
mutable base tags, so the measured inventory matters.

An exact `git archive` of the approved commit was extracted into an ignored,
task-owned directory. `npm ci` and frontend builds ran there, preserving the
developer's original node_modules, dist and untracked files. A private build
overlay used the existing P5 test Dockerfile instructions and excluded artifacts,
secrets, certificate material and dependencies from its context; it includes all
P0–P7 test sources. There are no cloud-local flattened dependency images or DNS
selection flags. Global builder/volume pruning was disabled.

The built-in source guard filters absolute paths containing `artifacts`; this
scratch location therefore makes that guard incomplete. An additional independent
comparison verified **122** Python/realm/requirements files inside the test image
against the archived source. All matched. The active application package inventory
also exactly matched the inventory supplied to pip-audit. See
[diagnostics/source hashes](final-dns-20261024-diagnostics.json).
All **223** tracked runtime/test files also have zero Git diff against the approved
commit: [preservation inventory](final-dns-20261024-preservation.json).

Initial physical free space was approximately 12.3 GiB on C: and 66.8 GiB on D:.
Subsequent measured space is recorded in command evidence. WSL's large sparse-disk
capacity is not extra physical free space. No unrelated images, containers or
volumes were pruned to obtain space.

## Real DNS and the exact three cases

| Case | Actual outcome | Evidence |
|---|---|---|
| P1 `test_public_dns_for_current_ssrf_validation` | PASS: original unittest assertion sees `True` from `socket.getaddrinfo('example.com',443)` in the actual backend network namespace | focused host result; repeated legacy run |
| P2 `test_https_ssrf_uses_real_dns_and_preserves_roles[staff-200]` | PASS: exact original pytest node, original database/users/header fixtures, HTTP 200 for `https://example.com/test` | focused JUnit; repeated legacy run |
| P2 `test_https_ssrf_uses_real_dns_and_preserves_roles[admin-200]` | PASS: same unchanged assertion and fixtures, HTTP 200 | focused JUnit; repeated legacy run |

The focused run `cloud-api-p3-7ed9c5da832f` ran on
2026-10-24 05:59:53–06:01:28 UTC (12:59:53–13:01:28 Asia/Saigon): **3 passed,
0 failed/errors, 0 expected failures, 0 skipped**. A later TLS diagnostic repeats
these same cases; it is not three additional unique acceptance cases.

Both `example.com` and `pypi.org` resolved on Windows, in a disposable bridge
container, directly inside FastAPI, and in a separate probe sharing FastAPI's
network namespace. They also resolved in the active OIDC backend. Windows used
its existing adapter resolver configuration; no VPN/DNS settings were changed.
The disposable bridge container used Docker's `192.168.65.7`; backend resolution
used `127.0.0.11` forwarding to that Docker resolver. Docker reported no DNS
override or extra_hosts. Exact commands, answers, resolver files and exit codes
are in [DNS diagnostics](final-dns-20261024-diagnostics.json).

Sandbox DNS access was denied during initial diagnostics; the actual host checks
were rerun outside that restriction and succeeded. One initial recorder command
had a PowerShell quoting error after successful DNS queries; its corrected command
exited 0. Neither issue is classified as a public-DNS outage.

The HTTPS cases use the existing legacy-suite JWT fixture appropriate to P3;
the active suite uses its original real Keycloak PKCE/token fixtures. All gateway
clients retain CA verification and upstream Kong-to-FastAPI mTLS. No public hosts
entries, IP substitutes, mocked DNS, certificate bypasses, skips, deselections or
new xfails were introduced. `backend/app/routes/security.py` only validates URL
syntax, allowed domain and every resolved IP; it does **not** download content.
DNS PASS is not proof of an outbound HTTP-fetch capability.

## Regression evidence and unresolved execution failures

The authoritative per-case results are in
[results](final-dns-20261024-results.json). Counts are per suite/run, not a sum of
repeated executions as unique tests.

| Run/group | PASS | Historical xfail | FAIL / error | Skipped |
|---|---:|---:|---:|---:|
| Focused original DNS cases |3|0|0|0|
| Legacy P0/P1 pytest |106|2|0|0|
| Legacy P2 HTTPS/business/socket pytest |85|2|0|0|
| Legacy P3 identity/mapping pytest |22|0|0|0|
| Legacy P1 host methods |15|0|1 error|0|
| Legacy P3 persistence/isolation methods |3|0|0|0|
| Legacy P2 host methods |2|0|14 failed methods|0|
| P7 attack/scenario pytest |23|0|0|0|
| P7 paired DB backup/restore and return |PASS|—|0|—|

Legacy `cloud-api-p3-7b47c48cd1cd` exited 1. There are **233 passed executions,
4 historical expected-failure executions, 14 failed methods and 1 error** across
252 scheduled methods/cases. The TLS unittest report contains 16 failure records
because one failed method has three failing subtests; those are not 16 distinct
failed methods. The four xfails are only D01/D02 repeated locally and through HTTPS,
not four new defects. P5 repairs for D03–D07 remain passing.

The legacy collector bound `/var/lib/docker/containers` to an empty WSL host
directory, so Promtail returned 500 readiness and did not prove ingestion. This
was a real failed check. A task-only read-only mount bridge subsequently made
only this archived lab's backend/Kong/Keycloak log directories visible to WSL.
It never copied, synthesized or directly pushed log events. Active Alloy then
tailed the actual files. Initial legacy collector failure remains in the record.

The TLS host group encountered connection-refused results after Kong restarts,
then cascading failures including an empty container ID. A fresh diagnostic reran
the unchanged first expired-client case and reproduced connection refused.
This is an unresolved restart/readiness execution problem; it is **not** an
expected baseline defect and is not evidence of a successful negative TLS test.
Its cause has not been isolated sufficiently to rule out an application or
dependency regression. Passing sub-assertions about denied TLS identities are
retained as observations, not promoted to passing whole methods.
Normal verified HTTPS/business and socket/client-certificate pytest cases passed,
but these successes do not replace the failed host/rotation assertions.

P7 `cloud-api-p7-060e950e1523` passed all 23 scenario tests and the paired recovery
drill (restored rows/constraints/owners/grants, genuine recovered PKCE/API access,
backend recreation, return to original lab databases). It then exited 1 while
recreating Alloy: merged collector overlays retained an old backend-container
log directory after its removal; Docker Desktop rejected the stale source mount.
Post-recovery monitoring and later groups of that driver were **NOT EXECUTED**.
They are not inferred from earlier P7 evidence.

The original unfiltered P6 runner was invoked separately to execute the remaining
active P4/P5/P6 groups. Its final results are recorded separately below and in JSON;
it does not turn the failed P7 driver into a passing run.

| Separate active P6 driver group | PASS | FAIL / gap | Skipped |
|---|---:|---|---:|
| P6 telemetry/audit/privacy/alert pytest |24|0|0|
| P5 hardening pytest |110|0|0|
| Full active OIDC / P2 / P1 pytest |144|1: `test_live_p4_global_rate_limit`|0|
| Focused OIDC subset (overlaps full suite) |1|2: rate-limit recovery and following health assertion|0|
| P4 network/DB/Alloy host checks |5|0|0|
| P3 identity persistence/isolation host checks |3|0|0|
| P2 TLS host methods |2|14 failed methods, 16 failure records including subtests|0|
| Alloy/Loki initial/restart/backend-outage lifecycle scripts |3 scripts|0|—|
| SDK browser and production-SPA browser helpers |0 completed browser assertion groups|Both helpers exit 1; missing gateway `8443/tcp` binding after TLS failures|—|
| Signing rotation/outage helper |1 staging phase|Next phase fails at Kong candidate config parse; remaining phases NOT EXECUTED|—|

`cloud-api-p6-c08966a13806` ran 06:21:59–06:42:29 UTC (13:21:59–13:42:29
Asia/Saigon), exiting 1. The full 145-case active pytest includes **both** original
SSRF/DNS staff/admin cases: both PASS with real Keycloak tokens. Its single failure
is the final `/health` HTTP-200 assertion after the rate-limit test's window wait.
The original assertion does not retain the actual response status; do not invent
one or relabel this as a DNS failure. The focused subset's following health case
also fails there but passes in the later full suite. These repeat runs overlap.
There are zero active xfails; no actual skipped pytest cases were introduced.

All six actual Grafana rules again observed inactive → pending → firing → inactive.
The four grouped queries measured webhook 9 (>3), ownership 8 (>3), SSRF 8 (>3),
and rate-limit events 12 (>5); controlled upstream errors measured 8 (>3).
The 30-second pending policy, 60-second windows and 10-second evaluation interval
were unchanged. Reduced real engine snapshots and queries are retained in results
JSON. Alert delivery outside Grafana was not configured or tested.

Node client (19 assertions), Node session lifecycle script and production frontend
build passed. Historical P6 retention evidence is unchanged and was not rerun here;
no new claim about two-hour production retention or external alert delivery is made.

## Connected dependency/advisory review

The scans used real advisory services, not the previous offline audit result.
See [complete version/findings inventory](final-dns-20261024-advisories.json).

| Scanner / scope | Outcome |
|---|---|
| pip-audit 2.10.1, all 61 installed application distributions, pinned inventory | Completed, exit 1: 66 reported advisory records in 9 packages; 35 distinct package/advisory-ID records after exact-ID deduplication. Alias overlaps remain. These are not 66 distinct exploitable vulnerabilities. |
| npm 11.9.0, committed lockfile, online audit | Completed, exit 1: 13 dependency findings (7 high, 6 moderate). |
| npm online production-dependency audit | Completed, exit 1: 4 dependency findings (2 high, 2 moderate). |
| Docker Scout 1.20.4, backend/Kong/Keycloak/PostgreSQL/Loki/Grafana/Alloy/nginx | Eight completed, unfiltered image scans returned findings; exact image references, severities, IDs, package URLs and reported fixes are in JSON. |

Scout's initial concurrent Keycloak/Grafana scans hit its cache lock; sequential
retries completed. Alloy's first registry request incorrectly selected the Windows
platform; its final scan explicitly selected the actual local linux/amd64 image.
These failed attempts are retained, not presented as clean scans.

Version matching is not reachability confirmation. The OIDC decoder fixes RS256
and validates issuer/audience/type; ECDSA signing and JWE decryption are not used
by that path, reducing relevance of some python-jose/ecdsa advisories. The SPA uses
browser Axios, so Node adapter/proxy findings are not automatically reachable in
the served browser bundle. Vite/build tooling is distinct from the nginx-served
production SPA. No server-side React Router hydration is implemented. These are
source-based scope observations, not blanket suppressions.

Starlette/python-multipart advisories require form-parser review; legacy login
uses OAuth2PasswordRequestForm, while the active gateway retires local issuance.
The known [Starlette multipart advisory](https://github.com/Kludex/starlette/security/advisories/GHSA-f96h-pmfr-66vw)
and [python-multipart advisory](https://github.com/Kludex/python-multipart/security/advisories/GHSA-59g5-xgcq-4qw3)
were checked against maintainer sources. Current PKI uses exact SANs, direct-issuer
enrollment and OpenSSL TLS; python-cryptography certificate-verifier advisories
still require API-specific review. pip/pytest/setuptools, vendored image packages,
vendor backports and high/critical infrastructure findings remain to be triaged.
No exploit was assumed solely from a package match; no clean vulnerability or
production-safety claim is made. No requirement, lockfile or infrastructure-version
pin was changed.

## Final gate and scope

| Gate | Decision |
|---|---|
| Three unique inherited DNS cases and backend real-DNS path |PASS|
| Previously passing source/security policy preserved |PASS: unchanged tracked runtime/test sources and independent image verification|
| All mandatory full regression/transport/rotation checks successful |BLOCKED: actual failures and execution gaps retained above|
| Dependency/image high/critical findings reviewed and resolved |BLOCKED: connected scans completed, actionable triage/remediation remains|
| Strict final release acceptance |BLOCKED|

No configuration was weakened to obtain DNS success. Failed TLS/recovery-driver
checks require investigation on this Windows/WSL platform or a supported plain
Linux runner, then the original full drivers must be rerun. Dependency fixes need
a separately reviewed change and regression validation. No benchmark, HA,
production cutover, Kubernetes or post-P7 feature work is implied.

Cleanup was verified for all five owned projects: no task containers, volumes or
networks remained. The temporary Docker Desktop/WSL log binds were also unmounted
and verified absent. Existing unrelated containers remained running. Installed WSL
test tools and ignored local evidence/image caches are retained; this is not a
global host/package cleanup. New PKI/credential temporary directories were removed
by the runners. [Cleanup checks](final-dns-20261024-diagnostics.json) record the
specific project filters and outcomes.

[Executed top-level commands](final-dns-20261024-commands.json) and the ignored local
`tests/p7/artifacts/final-dns-20261024/` directory retain detailed raw outputs,
runner argv, JUnit, source hashes and diagnostics. Public exports deliberately
exclude container inspection, credentials, tokens, PKI private material, raw
database dumps and request bodies. Public staged files receive a separate secret
review: [scope and results](final-dns-20261024-secret-review.json). Raw evidence
hashes and helper-source fingerprints are in the
[artifact manifest](final-dns-20261024-artifacts.json). The new documentation
commit's exact hash is supplied in the completion
report, avoiding a self-referential commit hash in this file.

Changed tracked content: this report; the seven `final-dns-20261024-*.json`
evidence files linked above; and a five-line follow-up link in `p7-results.md`.
Task orchestration/build helpers and the archived source tree remain ignored
local artifacts. No runtime file, security assertion or dependency pin is staged.
