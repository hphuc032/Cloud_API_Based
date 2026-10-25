# Final image remediation validation — 2026-10-25

**Functional/security regression: PASS for the tested linux/amd64 artifacts. Release: BLOCKED by unresolved advisory, lifecycle and builder risks.** No production data, existing production volumes, push or merge was used.

Starting commit: `0b86cf04b471662f7731efac8f2cb34066752441`, branch `migration/cloud-api-security`. Exact before/after images and the architecture are in [the image review](../security/final-container-image-review.md); individual decisions are in [the risk register](../security/final-image-risk-register.json).

## Environment and provenance

Windows/Docker/WSL/Python/Node versions, Docker resources and Git checks are recorded in [final-environment.json](../security/final-image-evidence-20261025/final-environment.json) and [Windows/disk metadata](../security/final-image-evidence-20261025/final-windows-environment.json). Docker Desktop4.73.1, Engine29.4.3, Compose5.1.3; Docker20CPUs/7.61GiB. Windows Python3.14.2/Node24.14/npm11.9; native WSL Python3.12.3/Node18.19/npm9.2. Host validation venv includes cryptography50.0.2, PyYAML6.0.3 and pip-audit2.10.1. Runtime backend Python3.11.17 is a separate container artifact. Linux Chromium145/Playwright1.58.2 and NSS/bwrap execute real browsers. Node18 is an acknowledged unsupported build-tool limitation, not a shipped nginx runtime.

Source snapshots were created in new native `/tmp/florasecure-final-image-*` directories so Docker bind permissions and Linux native npm modules are correct. No user untracked files were copied into commits or overwritten. Each original runner generated a random project, PKI, credentials and volumes. Desktop adapters scope log mounts to that project and use native UID1000, verified local CA trust and a private identity TCP relay. They do not mock public DNS or disable TLS.

Two Kong workers are a lab resource setting, not a change to authentication, limits or security assertions. No `--defer-public-dns`, test selection filter, ignore-base or policy suppression was used in the final full suites. Original P7 executes three focused checks again as part of its established orchestration; these are not counted as additional unique cases.

## Final complete results

| Mode / original runner | Suite | PASS | XFAIL | Unexpected failure/error | Required skip |
|---|---|---:|---:|---:|---:|
| Legacy `tests/p3/run.py` | P0/P1 in-process |106|2|0|0|
| Legacy | P2 HTTPS business/TLS pytest |85|2|0|0|
| Legacy | P3 identity |22|0|0|0|
| **Legacy total** | |**213**|**4**|**0**|**0**|
| Active `tests/p7/run.py` | P7 security |23|0|0|0|
| Active | P6 observability |24|0|0|0|
| Active | P5 hardening |110|0|0|0|
| Active | P4 focused repeat |3|0|0|0|
| Active | P4 regression |145|0|0|0|
| **Active execution total** | **302 unique pytest nodes + 3 repeated checks** |**305**|**0**|**0**|**0**|

The four historical legacy expected-failure executions are two inherited local-JWT defects, each exercised in-process and over HTTPS: missing `exp` accepted and malformed non-UUID subject causing500. They are preserved, not newly introduced defects or required skips. They remain distinct from active OIDC’s strict token semantics. No previously expected failure was silently converted by this image work.

| Additional original gate | Legacy | Active |
|---|---|---|
| Deployment/network/role host checks |16/16|5/5 P4 isolation/roles plus3/3 identity-host checks|
| Identity persistence host methods |3/3|included above|
| TLS/mTLS host methods |16/16|16/16|
| Multipart/urlencoded parser methods |5/5|5/5|
| SDK real-browser lifecycle |not an active-legacy gate|9/9|
| Production SPA/browser |not an active-legacy gate|8/8|
| Signing-key rotation/JWKS outage |not an active-legacy gate|6/6 recorded stages; final retired-key stage repeats the assertion|
| Paired app/identity restore, backend recreate, return to originals |legacy DB/adoption checks pass|PASS|
| Recreated Grafana/collector mounts and current ingestion |legacy Promtail ingestion PASS|PASS|
| Alloy/Loki restart positions, real alert outage/recovery |historical collector remains separate|PASS|
| Six real Grafana rule evaluations |historical stack not substituted|PASS|
| Cleanup |PASS|PASS|

The legacy final project is `cloud-api-p3-730041a2c873`; the active final project is `cloud-api-p7-ec3d3891d696`. Actual runner receipts:

- Legacy UTC: 2026-10-25T07:52:33.718876+00:00 → 2026-10-25T08:04:35.117530+00:00, exit0.
- Active UTC: 2026-10-25T07:51:48.031520+00:00 → 2026-10-25T08:21:23.547764+00:00, exit0.

[Every pytest node/result](../security/final-image-evidence-20261025/test-identifiers.json), [suite matrix](../security/final-image-evidence-20261025/regression-summary.json), original JUnit and host/browser/recovery reports are retained under [tests/](../security/final-image-evidence-20261025/tests/). All original active runner result keys and cleanup are0; deferred DNS list is empty. Earlier full pre-Alloy executions also passed but are not added to unique totals.

## Independent P0 fixture compatibility

After runtime pip removal, the standalone `tests/p0/run.py` inventory step still
called `pip freeze` inside backend. A caller audit found this blocker; it now reads
installed distributions through Python `importlib.metadata`, preserving package
inventory without reinstalling a runtime package manager. No API assertion changed.
The original independent HTTP/Kong fixture was then executed on its own new project
`cloud-api-p0-2799c48a3149`: **87 PASS + 2 historical JWT xfails**, cleanup PASS.
These89 executions repeat existing P0 scenarios and are not added to unique totals.
The actual JUnit/run/package/image inventory and exact command receipt are retained
under the `independent-p0-*` evidence files.

## Exact real-DNS cases

| Original case | Result / evidence |
|---|---|
| `test_public_dns_for_current_ssrf_validation` |PASS in the original16-method deployment host suite; actual backend namespace lookup|
| `test_https_ssrf_uses_real_dns_and_preserves_roles[staff-200]` |PASS in original P2 HTTPS pytest with real backend DNS|
| `test_https_ssrf_uses_real_dns_and_preserves_roles[admin-200]` |PASS in original P2 HTTPS pytest with real backend DNS|

Anonymous/customer roles and invalid/private IPv4/IPv6 targets also retain their original expected denial behavior. Both allowed cases submit `https://example.com/test`, using the existing suite authentication and verified Kong HTTPS/backend mTLS. Active OIDC regressions separately test allowed/denied SSRF roles. `backend/app/routes/security.py` calls `socket.getaddrinfo`, validates all returned addresses and returns metadata; it performs no remote content download.

Windows `Resolve-DnsName` and a disposable bridge container resolve `example.com` and `pypi.org`. The actual final FastAPI namespace also resolves both, using Docker resolver127.0.0.11, upstream192.168.65.7, no DNS overrides. Returned public IPv4/IPv6 values, commands, errors and resolver files are in [dns/](../security/final-image-evidence-20261025/dns/). One earlier exec attempt returned “container is not running” during deliberate restore quiescence; it was not a DNS failure and was rerun successfully. No public hosts-file entries, fixed public addresses or resolver bypasses were used.

## Negative TLS evidence

| Trigger | Actual boundary/result |
|---|---|
| Missing client certificate |TLS handshake/read rejected; no HTTP authorization response|
| Untrusted, expired or wrong-EKU client |TLS/SSL rejection; actual Kong client substitutions produce upstream502, not application401/403|
| Unenrolled client or invalid CA/client identity enrollment |Handshake rejection or backend startup refusal before listener, as appropriate|
| Backend expired certificate |Kong verified upstream502 / certificate-expired reason|
| Backend invalid chain |Kong verified upstream502 / unable-to-verify reason|
| Matching CN but wrong DNS SAN |Kong verified upstream502 / hostname mismatch|
| Backend wrong server EKU |Kong verified upstream502 / unsuitable purpose|
| Plain HTTP to backend TLS port / alternate plaintext port |No usable plaintext API listener|
| Gateway external HTTPS |Trusted edge CA + localhost SAN →200|
| CA/client/edge rotation and rollback |Overlap/mixed/new trust works; retired client/edge trust rejected; matching old set rollback→200|
| Vite and SPA trust |Correct CA succeeds; wrong CA fails. SPA exact wget health command exits0 with correct CA and5 with wrong CA|
| Monitoring |All four real upstream TLS validation failures collected by Alloy and queried from Loki; raw secret/error context excluded|

Original16-method evidence is retained for both modes. No `curl -k`, `ssl_verify=false`, insecure skip or equivalent bypass is acceptance evidence. A normal HTTP401/403 is never counted as a failed TLS handshake.

## Stateful upgrade and rollback drills

| Component | Actual isolated result |
|---|---|
| Loki2.9.8→2.9.17 |Old marker survives, new writes queryable, cold pre-upgrade copy restored with old image; PASS|
| Loki physical retention |Exact expired object disappears, current object hash unchanged, independent read-only querier old0/current1, writer queries and deletion metric succeed; PASS|
| Grafana10.4.2→10.4.19 |Seeded provisioned SQLite/dashboard state retained, new dashboard persisted, old image on cold pre-upgrade copy recovers only old state; PASS|
| Keycloak26.2.5→26.8.1 |Separate copied PostgreSQL volume; migration count152→237; realm/client/user IDs, edited displayName, RSA JWKS hash, application rows/mappings/owners and real PKCE/RBAC preserved; restart PASS; old image with original untouched DB rollback PASS|
| Alloy1.14.1→1.14.2 |Immutable production pipeline, no socket/caps, old positions retained, new event and restart preserve offsets; old image on cold positions copy continues ingestion. Actual read-line counters1/1/1/3 prevent Loki dedup hiding replay; PASS|
| Alloy harness failure cleanup |Docker start exit127 leaves a created container; corrected cleanup removes labelled owned container/volume, accepts already-absent resources and refuses a differently labelled disposable control; PASS|

[Focused drill reports](../security/final-image-evidence-20261025/focused/) and [physical retention](../security/final-image-evidence-20261025/retention/) retain actual image IDs, counts and cleanup codes. No old binary was assumed safe on a newly migrated data format; rollback uses a cold pre-upgrade copy/original DB. These are lab proofs, not a production recovery-time objective or live production migration.

## Executed commands and reproduction

[Command ledger](../security/final-image-evidence-20261025/command-ledger.json) records actual argv, timestamps/status and output hashes. [Scanner commands](../security/final-image-evidence-20261025/scan-commands.json) retain exact IDs, platforms and receipts, including failed cache-lock attempts. The final orchestration commands executed from the Windows workspace were:

```text
wsl -d Ubuntu -- bash -lc 'cd /mnt/d/MatMaHoc/Project_CLOUD_API && CANDIDATE_ROOT=/tmp/florasecure-final-image-final-20261025 _local_archive/final-remediation-tools-venv/bin/python tests/p7/artifacts/final-image-review-20261025/record.py full-active-final _local_archive/final-remediation-tools-venv/bin/python tests/p7/artifacts/final-image-review-20261025/run_candidate.py active'
wsl -d Ubuntu -- bash -lc 'cd /mnt/d/MatMaHoc/Project_CLOUD_API && CANDIDATE_ROOT=/tmp/florasecure-final-image-final-20261025 _local_archive/final-remediation-tools-venv/bin/python tests/p7/artifacts/final-image-review-20261025/record.py full-legacy-final _local_archive/final-remediation-tools-venv/bin/python tests/p7/artifacts/final-image-review-20261025/run_candidate.py legacy'
python tests/p7/artifacts/final-image-review-20261025/scan_final.py
python -m pip_audit --strict --disable-pip --no-deps -r backend/requirements.lock -f json -o tests/p7/artifacts/final-image-review-20261025/python-advisory.json
npm audit --json
```

The local ignored wrappers capture receipts and select the native source directory; they invoke the original `tests/p3/run.py` and `tests/p7/run.py` without test filters or DNS deferral. They clear inherited Compose/Pytest selection/reuse settings, set the already-reviewed Desktop log/browser/probe adapters, keep build-cache pruning disabled, use two Kong workers and place large image-audit temp files on D:. They do not replace assertions. Wrappers/raw private lab artifacts are not required in a clean clone.

For a new operator reproduction, create a **new native WSL checkout/export**, install the documented host dependencies/Chromium/NSS, `npm ci` in frontend and use the repository runners with these lab settings:

```sh
export CLOUD_API_DESKTOP_LOGS=1 CLOUD_API_DESKTOP_BROWSER=1 CLOUD_API_KEEP_PROBES=1
export P4_RELEASE_BUILD_CACHE=0 P3_RELEASE_BUILD_CACHE=0 P4_RELEASE_EXITED_JOBS=1
# A new temporary overlay containing only kong.environment.KONG_NGINX_WORKER_PROCESSES='2'
# can be supplied as both P4_BUILD_OVERLAY and P3_BUILD_OVERLAY on a small host.
# Set P1_IMAGE_AUDIT_TMPDIR to a new temporary directory on a drive with capacity.
python tests/p3/run.py
python tests/p7/run.py
python tests/p6/retention.py
python tests/p7/image_upgrade.py --component loki --old-image sha256:8b5bd7748d0e4da66cd741ac276e485517514af0bea32167e27c0e1a95bcf8aa --new-image sha256:c4a25af6f2709fa625d88ee5df494a332a85f30e9575854031667823ecc5be04
python tests/p7/image_upgrade.py --component grafana --old-image sha256:7d5faae481a4c6f436c99e98af11534f7fd5e8d3e35213552dd1dd02bc393d2e --new-image sha256:a9043254ba16fb10945cc27333963dfd08eccbb43b51f1222d831cc564e3a1f4
python tests/p7/alloy_upgrade.py
python tests/p7/run.py --focus recovery --identity-upgrade-from quay.io/keycloak/keycloak:26.2.5@sha256:4883630ef9db14031cde3e60700c9a9a8eaf1b5c24db1589d6a2d43de38ba2a9 --identity-upgrade-to quay.io/keycloak/keycloak:26.8.1@sha256:a78d6b79572168cb25886b80a8b5b8d4ed4390743e3eecb810538683e209dd6b
```

These are reproduction instructions, not additional claimed executions. The cold identity helper validates its own random P7 project, official pinned image refs and disposable DB name; it cannot select a production DB/volume. Original retention runs independently of full P7 and must not be omitted for a Loki change. Scans must target actual newly built runtime IDs if a rebuild changes them.

## Dependency advisory findings

Connected pip-audit2.10.1 exit1 completed: five raw entries, three unique issues—ECDSA Minerva CVE-2024-23342 (duplicate source records), pytest CVE-2025-71176 (duplicate records, CNA medium6.8), and python-jose DER/HMAC confusion CVE-2026-85394. Those are advisory findings, not a failed advisory service. No fixed python-jose/ecdsa release was available in the queried PyPI metadata. Strict active RS256 and separate legacy HMAC keys are recorded counterevidence, not formal risk acceptance.

Connected npm11.9 audit exit1 completed: five moderate affected-package entries (`postcss-nested`, `postcss-selector-parser`, `react-router`, `react-router-dom`, `tailwindcss`), no HIGH/CRITICAL. Transitive effects are not five independent underlying advisories. Reported fixes include major Tailwind/Router changes; no automatic major update was performed. Both complete raw reports remain under [dependencies/](../security/final-image-evidence-20261025/dependencies/).

Runtime pip/vendor removal is verified by import checks, final SBOM and exact-image scan. It does not retroactively secure build-time pip26.2. Upstream26.2.2 vendor comparison updates certifi only among the reported vendors; the builder retains hash-locked binary-only/no-cache controls and no supplied index credentials/build secrets, with residual review left open. JDK/OS/compiled libraries and all Go modules are inventoried through exact-image SPDX; scanner package labels do not prove linked-symbol reachability or complete coverage of compiled crypto.

## Failed attempts and uncertainty retained

- Initial Docker Desktop was stopped. After startup the environment checks completed; unrelated existing containers were not changed.
- Parallel Scout shared-cache lock timeouts were retried sequentially; all eight final scans completed exit0. No incomplete scan is presented as successful.
- Raw slim nginx lacks GNU wget’s `--ca-certificate`; the rejected candidate was replaced by the verified derived image.
- Kong image UID1001 could not read existing mode0600 UID1000 keys. The first tmpfs attempt obscured packaged `/usr/local/kong/lib` and failed loading ada. Final `/run/kong` prefix preserves those libraries and non-root UID1000 without broadening key access.
- Two early P6 limiter focuses failed an expected401 assertion without recording the actual status. A later passing diagnostic captured a burst at second59; the bounded shared wait preserves all request/assertion counts. Final24 P6 +110 P5 and the whole suite pass.
- Initial P7 browser focus also reused fixture state and failed binding; the correct original P5 browser focus passed. Final normal P7 browser lifecycle passes.
- The first storage probe incorrectly assumed internal-network host publishing; the corrected namespace client leaves the network internal. Cold upgrade/rollback then passes.
- Early identity drill setup used an invalid empty feature-disable value, then hit the Kong UID issue; neither executed a successful migration. The corrected cold migration/rollback helper passed. In its expanded run, the subsequent standard paired-restore backend-recreation `/auth/me` assertion failed without a captured HTTP status; its root cause remains unproven. Both subsequent full normal active runs, including final recovery/recreation, pass. The earlier failure is retained, not relabelled as an expected failure.
- A separate exact-artifact DNS/transport focus reused a SHA-addressed test image without the original helper’s project-local test-image alias, causing two namespace probes to exit125 before assertions. Its backend DNS exec succeeded and matched the scanned artifact. The normal final runners build their required aliases and pass; this operator-wrapper error was not “fixed” by weakening network isolation.
- Independent Alloy review found and reproduced create-success/start-failure cleanup leakage. The final helper’s ownership-checked cleanup was verified with real Docker failures and a separate full positions/rollback rerun after the mandatory-suite source snapshot. The P0 package-inventory caller was also independently corrected/tested; no runtime or mandatory API/security assertion changed after that snapshot.
- Previous pre-Alloy full active focused tests have a long wall-clock pause. Their timing is not a performance result. Final active complete runtime is approximately30minutes; no latency/SLO claim is made.

## Evidence safety, files and release gate

Curated evidence excludes raw container environments, private key/certificate bundles, CA signing keys, identity/password fixtures, full tokens, browser profiles and DB/role-verifier exports. Original source-guard SHA fields are retained. Gitleaks8.30.1 reported six generic-key matches in them; all six equal recomputed source-file SHA256 values. They are verified false positives, not an ignored secret finding; no suppression was added. See [secret review](../security/final-image-evidence-20261025/secret-review.json). Final staged/commit diff and secret review are recorded before completion.

Changed implementation files are limited to backend Dockerfile; base/P5/P6 Compose and nginx build context; independent P0 Kong fixture; P2 runtime-prefix test path; P0 package inventory plus P0/P4/P5/P6 timing/browser compatibility helpers; Loki retention pins; P7 isolated upgrade helpers/runner flags. No application business/authentication source or Alembic migration was changed. Live deployment notes receive dated version/UID clarifications; historical P0–P7 evidence remains intact.

Release gates: regression/real DNS/HTTPS-mTLS/OIDC/RBAC/ownership/webhook/SSRF/monitoring/recovery PASS; image/advisory/lifecycle/builder risk closure **BLOCKED**. This report supplies no owner risk acceptance and no authorization to push, merge or deploy.

## Local commits and reviewed diff

- Image/runtime/configuration: `b6a4c5533b25596ea120603e612a0eb62ff0d77a`.
- Test compatibility/upgrade/rollback harnesses: `c4ef9c796c65e31c23d0d85d64caffe01d62fb50`.
- Author/committer: Nguyen Hoang Phuc `<nhpntd@gmail.com>`.

The implementation range changes20 files,660 insertions and35 deletions.
Application business/authentication source, Alembic migrations, frontend source,
gateway policies and monitoring pipeline/rules are unchanged; exact paths and
per-commit files are in [Git review](../security/final-image-evidence-20261025/git-review.json).
[All implementation files](../security/final-image-evidence-20261025/files-changed.json)
and [the evidence checksum manifest](../security/final-image-evidence-20261025/manifest.json)
provide the complete created/modified-file inventory. Documentation/evidence is a
separate local commit; its exact SHA is reported at completion rather than embedded
in its own content. Git diff checks pass. Gitleaks scanned both implementation
commits with zero findings; staged evidence matches are the six verified source
hashes described above. No real secret was found in the reviewed changes.
There was no push, merge, reset/rebase/amend or production deployment.

## Git-history secret-scan follow-up

The post-commit Git scan examines a different input context from directory/staged
file scanning. Gitleaks8.30.1 returned778 findings: six generic-key matches in
source-integrity SHA256 fields,716 Sourcegraph-rule matches in SPDX file SHA1
checksums, and56 in SPDX package-verification fields. Its
[official rule](https://github.com/gitleaks/gitleaks/blob/v8.30.1/cmd/generate/config/rules/sourcegraph.go)
accepts unprefixed40-hex strings when its keyword is present; the Alloy SBOM
contains a Sourcegraph module name. Do not mistake the nonzero scanner exit for
778 confirmed credentials, or report it as a zero-finding scan.

All716 file values were recomputed from stopped containers created from the
exact original/final Alloy images, using streamed Docker exports without mounts,
extraction, service execution or production data. All56 package-verification
codes were independently reproduced by Scout for those same exact images after
removing Sourcegraph-named environment inputs. These package codes are reproduced
metadata, not a claim that the complete package-owned-file SPDX verification
formula was reconstructed from the partial evident-file relationships. The six
source SHA256 values match source bytes. No real credential was found and no
scanner suppression/allowlist or raw SBOM edit was added.

[Per-match verification](../security/final-image-evidence-20261025/git-checksum-dispositions.json)
and [the secret review](../security/final-image-evidence-20261025/secret-review.json)
retain the classification, exact image IDs/commands and individual locations.
Only labelled disposable verification containers were created and removed.
This evidence is a separate documentation-only follow-up commit; existing commits
were not amended. Release risk and every runtime/test result remain unchanged.
