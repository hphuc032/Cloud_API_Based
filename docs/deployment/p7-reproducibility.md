# P7 reproducibility

This is a disposable single-node Compose lab, not an approved production release.
Start at approved P6 `45e025703f6a193aeb5738632d436d52146f12de`; use the P7 commit
and verified transfer manifest identified in the completion report. Never reset a
dirty checkout. Verify `git status`, `git rev-parse HEAD`, and commit ancestry first.

## Tested entry points

Required: Linux Docker Engine/Compose (Compose must support `!reset`), Python3.11+
with cryptography (`docker/pki-requirements.txt`), Node/npm with locked frontend
dependencies, Chromium and certutil/NSS for browser tests. Legacy selection helper
also needs PyYAML. Actual tool/image versions and source hashes are in P7 evidence.
The runner generates negative PKI only inside a private temporary lab directory.
Do not use those certificates in production or install their CA into system trust.

```sh
python3 tests/p7/run.py --defer-public-dns
python3 tests/p7/legacy.py --defer-public-dns
node tests/p3/test_client.mjs
node tests/p4/test_session.mjs
```

The user explicitly deferred the three real-DNS cases for this P7 run. The flag
selects all other tests and records deferral; it never changes an assertion,
converts a failure to xfail, injects public DNS answers or relaxes TLS/SSRF.
Remove that flag for strict validation after the environment resolver is repaired.
A zero process exit with deferrals is **not** strict release acceptance.

`--focus recovery` runs only P7 scenarios, paired fresh-instance recovery and
monitoring restart; it supplements the full run. Other focus modes retain P6's
browser/rotation/hardening/telemetry/transport recovery semantics.

Each run creates a random `cloud-api-p7-*` project, fresh namespaced volumes and
networks, runtime-generated secrets, separate application/identity PostgreSQL and
new CA/leaf keys. Bootstrap and Alembic complete before API startup. Keycloak
imports the P5 realm on a new identity volume; reviewed synthetic issuer/subject
mappings are explicit. Kong receives public JWKS only. Current source hashes are
checked inside the test container before tests. The driver exercises the P4/P5/P6
candidate overlays, HTTPS discovery, backend mTLS, OIDC browser lifecycle,
production SPA build/CSP, logging and provisioned Grafana. It cleans only its own
project in `finally`; do not replace that with global volume pruning.

## Cloud-local execution versus portable build

The actual cloud host has a32GB filesystem and Docker vfs. Its previously verified
flattened dependency images and read-only current-source test mounts avoid copying
large dependency filesystems repeatedly. Actual wrapper environment:

```sh
export DOCKER_CONFIG=/workspace/.docker-config
export P4_BUILD_OVERLAY=/workspace/.cloud-api/p6-build.json
export P5_SOURCE_OVERLAY=/workspace/.cloud-api/p5-mounted-source.yml
export P5_TEST_BASE_IMAGE=cloud-api-tests-flat:verified
export P5_PROBE_BASE_IMAGE=cloud-api-backend-flat:verified
export CLOUD_API_KEEP_PROBES=1
python3 tests/p7/run.py --defer-public-dns
```

These cloud-local files/images are not portable dependencies shipped by Git. Their
image IDs/provenance and runtime source guard are evidence of what ran; they do
not prove an Internet rebuild from current upstream registries. Use the normal
tracked Dockerfiles on an adequately provisioned connected host, or securely import
verified dependency images with their matching public manifests. Neither bypass
TLS nor blindly trust a similarly named image. For legacy, use the recorded
P3_BUILD_OVERLAY/P3_SOURCE_OVERLAY/P3_TEST_BASE_IMAGE/P3_PROBE_BASE_IMAGE wrapper.
The successful legacy run sets P3_SOURCE_OVERLAY to the same current
`/workspace/.cloud-api/p5-mounted-source.yml`; the older legacy test-context lacked
P7 and was rejected by the source guard before any cases ran.

## Existing installations and production prerequisites

The new-deployment secret generator refuses overwrites and must never be run on
an existing installation. Existing-data adoption uses the separately documented
[P1 procedure](p1-deployment.md), [P3 identity infrastructure](p3-identity.md),
[P4 reviewed bindings/cutover](p4-cutover.md) and [P6 observability](p6-observability.md).
Keep project/volume identity, existing keys/secrets, stable issuer, users.id and
ownership relationships. Existing realm imports are skipped; apply reviewed
client changes privately, never delete the realm volume to force import.

The fully automated test deployment is an isolated OIDC candidate, not historical
legacy default deployment and not a production cutover. Before production:
resolve the acceptance matrix, current dependency/image advisories, real DNS,
real CA issuance/renewal, issuer/origin/callback ownership, reader permissions,
HTTPS Grafana management, named administration, protected off-host backups and
operational recovery objectives. File secrets are not an encrypted vault; private
SQL networks are not SQL TLS or directional egress firewalls. Do not use test-only
Chromium `--no-sandbox` as a production browser policy.
