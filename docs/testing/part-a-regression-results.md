# Part A — Regression and inspection results

2026-10-26; baseline `d79cb6060e95ba58cd797b6ef24b3b938ae80b8a`.
**No post-upgrade functional acceptance is claimed. Full regression NOT EXECUTED.**
See [decision and resource gate](../security/part-a-controlled-remediation.md).

## Actually executed

| Check | Actual result | Interpretation |
|---|---|---|
| Branch/HEAD/ancestor | expected branch and exact baseline; exit 0 | PASS preflight |
| Docker/Compose/WSL/dependencies/resources | recorded in preflight receipt | Tools available; full-stack resource gate not met |
| Kong 3.9.3 build/linkage/hash + FFI | 2 executions, exits 0 | OpenSSL 3.2.3 confirmed |
| Kong 3.9.4 build/linkage/hash + FFI | 2 executions, exits 0 | Still OpenSSL 3.2.3; lifecycle gate BLOCKED |
| Loki 2.9.17 / 3.7.8 version commands | 2 executions, exits 0 | Versions read from real linux/amd64 binaries |
| Copy/read compiled Go metadata | 2 binaries; hashes/module versions recorded | Artifact inspection, not exploitability test |
| Loki 2.9.17 unchanged config validation | exit 0 | Syntax PASS only |
| Loki 3.7.8 unchanged config validation | exit 1 | Candidate INCOMPATIBLE: two removed shared_store fields |
| Three pinned candidate registry descriptors | exits 0 | Platform metadata recorded, not signature verification |

There were eight successful-command/expected-outcome **container executions**:
four Kong, two Loki version commands, two config validators; one of those eight
returns exit 1 as the documented incompatibility. This is **seven exit-0 and one
exit-1 executions**, not eight passing security regression tests. Lifecycle and
advisory gates remain failures despite successful version commands.

An earlier exploratory Kong command failed on read-only `/tmp`; its standalone
Docker exit code was not captured, so it is not invented or included above.
The subsequent recorded version commands used a 16 MiB tmpfs. Nothing disabled
TLS verification. Create/copy/ownership/remove commands for two unstarted binary
copy containers all exited 0. No data volume was involved.

Exact argv/stdout/stderr/exits:
[Kong](../security/part-a-evidence-20261026/kong-crypto-inspection.json),
[Loki binary](../security/part-a-evidence-20261026/loki-binary-inspection.json),
[Loki config](../security/part-a-evidence-20261026/loki-config-validation.json),
[registry](../security/part-a-evidence-20261026/registry-metadata.json),
[preflight](../security/part-a-evidence-20261026/preflight.json).

Image downloads actually executed (both exit 0, no activation):

```powershell
docker pull --platform linux/amd64 kong:3.9.4@sha256:aa4a4687b1330e427ad0d3b27a0606b833894297c78abf1a212edc9ba73c8620
docker pull --platform linux/amd64 grafana/loki:3.7.8@sha256:1107dd5274e0ada47e42472b7a7e71f3b2a2fe878878108f3e2f9e51528f0193
```

For replay, use the recorded container argument arrays with a **new unique name**,
resolve a local image ID to its matching pinned repository descriptor, and replace
only the explicitly sanitized path placeholders. Binary metadata can independently
be checked with `go version -m` after `docker cp` and SHA256 verification. That
independent Go CLI check was not executed here; the offline parser result is the
actual evidence. No ignored helper file is necessary to identify the artifacts.

## Required regression matrix

| Group | Historical evidence only | Fresh Part A result |
|---|---|---|
| Legacy P0/P1/P2/P3 / historical collector | 213 PASS + 4 historical XFAIL executions | NOT EXECUTED |
| Active OIDC P4/P5/P6/P7 | 305 PASS executions / 302 unique cases | NOT EXECUTED |
| TLS/mTLS host methods | 16/16 per applicable mode | NOT EXECUTED |
| Browser SDK | 9/9 | NOT EXECUTED |
| Production SPA | 8/8 | NOT EXECUTED |
| Real DNS original cases | 3/3 | NOT EXECUTED |
| Rotation / outage | 6 recorded phases (includes repeated verification) | NOT EXECUTED |
| HTTP malformed/oversized bounded queries | No fresh candidate claim | NOT EXECUTED |
| gRPC bounded transport / required internal RPC | No fresh candidate claim | NOT EXECUTED |
| Alloy ingestion/recreate, dashboards, six alert transitions | Prior monitoring evidence retained | NOT EXECUTED |
| Loki retention, physical expiry, current-object hashes | Prior retention evidence retained | NOT EXECUTED |
| Cold-volume backup / upgrade / rollback | Prior recovery evidence retained | NOT EXECUTED |
| Exact final image vulnerability rescans | Historical Oct 25 only | NOT EXECUTED |

No tests were modified, filtered into a passing result, marked new XFAIL, or
silently skipped. These suites were **not started**, so no new pytest pass/fail/
skip count exists. The four historical legacy XFAIL executions are not new
defects. No post-change DNS, certificate, authentication, business-policy,
isolation or database-grant PASS is inferred from unchanged code. Grafana local
rule transitions, even when later retested, cannot establish external delivery.

## Reproducible continuation (not executed)

Run sequentially from an owned, clean native WSL source snapshot with separate
unique Compose project names, credentials, PKI and volumes. Do not reuse existing
application volumes. Review runner defaults before execution; clear inherited
Compose project/volume variables and pytest selection/reuse/DNS-deferral flags.
Keep security assertions and full case selection unchanged.

Documented Docker Desktop adapters for these runners:

```sh
export CLOUD_API_DESKTOP_LOGS=1 CLOUD_API_DESKTOP_BROWSER=1 CLOUD_API_KEEP_PROBES=1
export P3_RELEASE_BUILD_CACHE=0 P4_RELEASE_BUILD_CACHE=0 P4_RELEASE_EXITED_JOBS=1
python3 tests/p3/run.py
python3 tests/p7/run.py
python3 tests/p6/retention.py
```

Do **not** set either build-cache release flag to 1: that runner path can invoke
global builder pruning. If needed, `P1_IMAGE_AUDIT_TMPDIR` must be an owned
directory on a disk with sufficient space. Worker-count overlays must be reviewed
and scoped only to disposable Kong processes; no assertion/security weakening.

The existing `tests/p6/retention.py` pins the old Loki writer/reader, and
`tests/p7/image_upgrade.py --component loki --old-image <pin> --new-image <pin>`
uses the baseline config for both images. They cannot validate a 3.x candidate
unchanged. A future qualified candidate needs reviewed fixture parameterization
for target config/health/storage while preserving original checks, followed by
independent old-data/expiry/rollback evidence. No such adaptation was needed or
performed in this blocked research run.

Run full baseline first, then each qualified component candidate, then the combined
stack and rollback. Record scanner/advisory versions and timestamps and immutable
image hashes. Failed/skipped mandatory checks keep acceptance BLOCKED.
