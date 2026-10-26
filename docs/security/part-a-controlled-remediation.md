# Part A — Controlled security remediation

Date: 2026-10-26. Branch: `migration/cloud-api-security`.
Starting commit: `d79cb6060e95ba58cd797b6ef24b3b938ae80b8a`.
**Part A: BLOCKED. Overall production release: BLOCKED.**

This is a research and bounded artifact-inspection result, not a deployment or
validated security fix. Runtime source, Compose, authentication, TLS, database
roles, networks, storage, collectors and tests remain unchanged. No user service
was started/stopped and no existing database or volume was attached to inspections.

## Candidate and stage decisions

| Candidate | Actual evidence | Decision |
|---|---|---|
| Kong OSS 3.9.4, official image | Linked OpenSSL 3.2.3, same unsupported public lifecycle as 3.9.3 | Reject as REL-001 remedy; no qualified crypto maintenance established |
| Maintained OSS crypto rebuild / support backport | No reproducible, maintained, supported artifact established | No image invented or activated |
| Loki 3.7.8, official image | Go 1.26.6 / grpc-go 1.83.2 meet REL-002/003 floors; Go and x/net remain affected by REL-004; old config fails | Reject for acceptance; partial binary-level patch evidence only |
| Loki 3.6.17, source/registry review | Source Go 1.26.5 / grpc-go 1.83.2 / x/net 0.58.0; binary not inspected | No better qualified alternative established |
| Maintained Loki 2.x backport | No exact qualifying vendor artifact verified | Keep unresolved |

| Stage | Actual outcome |
|---|---|
| A0 research | Official releases/advisories and exact candidate metadata reviewed; no candidate qualified for activation |
| A1 Kong | BLOCKED recorded before further Loki configuration work; build/linkage/FFI checks completed |
| A2 Loki | Independent binary and config inspection only; REL-002/003/004 remain BLOCKED |
| A3 final scans | NOT EXECUTED: no final candidate and resource gate |
| A4 full regression | NOT EXECUTED: no stable candidate pair and insufficient demonstrated host headroom |
| A5 rollback experiments | NOT EXECUTED: no deployment/storage change; future procedure documented |
| A6 risk status | Separate unresolved-status record; historical risk register and scans preserved |

## Resources and boundary

[Preflight receipts](part-a-evidence-20261026/preflight.json) verify branch/HEAD,
ancestry, Docker Engine/CLI 29.4.3, Compose v5.1.3, WSL 2.5.9.0 / kernel
6.6.87.2-1, Windows 11 build 26300, Python 3.12.3 / Node 18.19.1 / npm 9.2.0 in
Ubuntu. Docker reports 20 CPUs and 7.61 GiB RAM. Initial Windows available RAM
samples were 0.96, 0.94 and 0.89 GiB; a later sample was 1.40 GiB. WSL reported
about 6.7 GiB MemAvailable, which is not proof of enough physical host headroom.
Latest recorded free disk was about 19.56 GiB on C and 44.07 GiB on D.

The task explicitly requires stopping resource-intensive work in this situation.
No full clean baseline, builds, image vulnerability rescans, full Compose stacks
or retention stress tests were started. Lightweight inspections used network-none,
read-only containers capped at 128 MiB, 0.5 CPU and 48 processes. Two official
candidate images were downloaded for inspection and remain inactive in Docker's
local cache. Copied Loki binaries and temporary helpers are ignored artifacts,
not committed source or evidence dependencies.

## Evidence and reproducibility

- [Kong support/linkage assessment](part-a-kong-openssl-assessment.md): exact digests, FFI and dynamic linkage.
- [Loki advisory/config assessment](part-a-loki-vulnerability-assessment.md): exact binary hashes, compiled modules, config failure.
- [Executed checks versus unexecuted regressions](../testing/part-a-regression-results.md): commands, exit codes, historical comparison.
- [Future upgrade/rollback gates](../deployment/part-a-upgrade-rollback.md): isolated data and recovery conditions.
- [Machine-readable risk status](part-a-risk-status.json): separate dispositions for REL-001/002/003/004.
- [Registry/platform receipts](part-a-evidence-20261026/registry-metadata.json): exact pinned references and platform manifests.
- [Final repository checks](part-a-evidence-20261026/repository-verification.json): privacy, preservation, integrity and secret scan.

Command arrays preserve arguments, outputs and exit codes; local paths are
replaced only where indicated by `<repository-root>` / `<ignored-work-dir>`.
Disposable container names/IDs are retained to correlate create/copy/remove
provenance; they are not persistent host identifiers or credentials. Runtime ASLR
addresses are omitted. No PEM keys, generated credentials, real access tokens,
raw SBOMs or new SARIF dumps are included.

For Git-tracked evidence, committed blob bytes are authoritative. No Windows
working-tree checksum is presented as a Git blob hash. Existing 149-entry
historical manifest is unchanged; Part A receipts are new, separate evidence.

## Historical references and unresolved release gate

The read-only local `final-release-blocker-priorities.md/.json` and
`final-release-blocker-traceability.md` reports were read and preserved untracked.
They are not required to follow this committed report: starting counts and issue
identifiers are restated here, with tracked provenance in the
[image review](final-container-image-review.md),
[risk register](final-image-risk-register.json),
[historical manifest](final-image-evidence-20261025/manifest.json),
[image regression record](../testing/final-image-remediation-results.md) and
[acceptance record](../testing/final-acceptance-remediation.md).

Historical core-image scan: 358 HIGH/CRITICAL rows (65 CRITICAL, 293 HIGH),
including Kong 0 and Loki 96 (18 CRITICAL, 78 HIGH). **Part A after-scan counts:
NOT SCANNED**, never zero. Kong's zero historical count does not resolve lifecycle.
The prior assessment's 267 remaining runtime HIGH/CRITICAL rows and five build-only
rows retain their dispositions; none is silently closed by this work.

No production approval or owner risk exception was granted. To resume, establish
a maintained Kong OSS crypto path (or separately authorize an edition/gateway
proposal), identify a Loki artifact covering REL-004 as well, and provide enough
host resources for fresh baseline/candidate/rollback runs. More RAM alone does
not fix candidate support or vulnerable dependencies. This work stops at Part A;
there is no push, merge, production deployment or Part B.
