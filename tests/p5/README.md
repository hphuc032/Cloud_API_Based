# P5 isolated validation

Use a reviewed P4 checkout with the P5 changes, Docker Compose v2, Python dependencies from backend/requirements.txt, Node/npm with frontend/package-lock.json, and Chromium/certutil for browser checks. Do not point fixtures at existing application data. The destructive baseline fixture explicitly requires APP_ENV=test, P0_ISOLATED=1 and postgres/p0_baseline.

```sh
npm ci --prefix frontend
node tests/p4/test_session.mjs
npm run build --prefix frontend
python3 tests/p5/run.py --focus hardening
python3 tests/p5/run.py
# Separate legacy-authentication regression (never the active OIDC release):
python3 tests/p3/run.py
```

The P5 runner creates UUID Compose projects, fresh secrets, both private PostgreSQL databases, PKI and reviewed identity fixtures. It verifies built Python source hashes, imports an ephemeral test signing provider, parses/reloads actual Kong configuration and records results in ignored `artifacts/`. Normal execution covers P5 API/gateway checks, P4/P2/P1 candidate regressions and network/TLS host probes, a production-built SPA browser flow and signing-key rotation. It always tears down only its own project and volumes. Focused execution does not replace the full regression.

`P4_BUILD_OVERLAY` may supply an environment-local build override, e.g. a previously verified dependency image, without changing security configuration. `P4_RELEASE_BUILD_CACHE=1` and `P4_RELEASE_EXITED_JOBS=1` bound Docker vfs disk consumption. Record the overlay and source evidence with results. Never use cached images with stale app/test source. Focused hardening skips observability startup; full validation retains its host ingestion check. The main P4 runner remains independently available for detailed SDK lifecycle/state/nonce tests.

Gateway tests intentionally consume peer-IP fixed-window budgets and wait for fresh windows. Do not run these against a shared gateway. Negative certificate tests must reach actual TLS listeners. External DNS tests remain real even when deterministic address tests pass. Report environment failures separately, retaining their original assertions and exit codes.

See [P5 results](../../docs/testing/p5-results.md) for actual executed outcomes and [design](../../docs/security/p5-design.md) for demo safety, schema, limitations and rollback. A successful frontend build alone is not browser validation.

On a copy-heavy vfs host, `P5_TEST_BASE_IMAGE` plus a `P5_SOURCE_OVERLAY` can use a previously verified dependency image with read-only sanitized `/app`, `/tests` and realm mounts, avoiding a duplicate image layer. The driver tags that image only under its disposable project name and checks source hashes. Set `P5_PROBE_BASE_IMAGE` to a verified smaller Python image for subsequent namespace probes, browser setup and rotation. The API pytest process finishes before this switch; authentication settings, certificates and mounted source are unchanged. The corresponding legacy runner options are `P3_TEST_BASE_IMAGE`, `P3_SOURCE_OVERLAY` and `P3_PROBE_BASE_IMAGE`. Keep the PostgreSQL-client image for legacy database/backup and TLS pytest phases. Record image IDs and do not use a local image alias as proof of official registry provenance.
