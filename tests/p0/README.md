# P0: current-implementation regression baseline

Run from the repository root with Python 3.9+ and Docker Desktop/Engine with Linux
containers and Docker Compose v2+:

```powershell
python tests/p0/run.py
```

The first run needs registry, Debian package repository and PyPI access. Application
dependencies come from the existing `backend/requirements.txt`; tests run on Python
3.11. PostgreSQL 16 and Kong OSS 3.8 match the current deployment's major versions.
No host Python packages or application `.env` files are needed.

The runner creates a randomly named `cloud-api-p0-*` Compose project. It generates
ephemeral database/JWT/webhook secrets in process environment, publishes no host
ports, uses a private project network and disposable PostgreSQL tmpfs, and removes
only that project's containers/network/volumes in `finally`. Existing stacks and
data are not touched. Database fixtures additionally require `APP_ENV=test`,
`P0_ISOLATED=1`, host `postgres`, and database `p0_baseline`. Do not run these fixtures
against an existing application database or in parallel against the same database.

Application schema creation uses `alembic upgrade head`, never `create_all` or the
reference SQL schema. Tests use the real FastAPI dependencies and real PostgreSQL;
authentication/RBAC/ownership are not mocked. User passwords are generated at runtime.
The role-matrix fixtures mint current-format JWTs; separate login tests exercise the
real password endpoint and its tokens. DNS responses alone are mocked to make SSRF
validation deterministic and avoid contacting external/internal destinations.

The Kong test mounts the unmodified `gateway/kong.yml`, checks forwarding to the
running Uvicorn backend, exhausts the actual 60/minute limit, observes 429 and Retry-After,
and verifies the limit applies across routes. A new gateway gives each run fresh
counters. It can wait up to 15 seconds to avoid starting a burst at a minute boundary.

Migration checks create separate empty databases, upgrade/idempotently upgrade,
verify tables/FKs/triggers, downgrade to base, and upgrade again. Template generation
occurs in a temporary copy, never in the repository. Backup verification uses actual
PostgreSQL 16 `pg_dump -Fc` and `pg_restore --exit-on-error` into another empty database;
it compares every row in all application tables and the Alembic revision, including
application UUIDs and user/order/product relationships. Dumps exist only inside the
disposable test container. This is a functional backup exercise, not production RPO/RTO
or disaster-recovery certification.

Results are written to ignored `tests/p0/artifacts/`:

- `pytest.txt`: pytest console output and expected-failure reasons.
- `junit.xml`: machine-readable results; expected failures are represented as skipped
  with `pytest.xfail` metadata, not successful security checks.
- `images.json`: Compose runtime image identifiers.
- `backend-packages.txt`, `tests-packages.txt`: resolved Python dependency versions.
- `run.json`: unique project, test exit code, cleanup status.

Do not commit generated artifacts, database dumps, environment files or runtime
tokens. The reviewed summary is committed in `docs/testing/p0-baseline.md`.

Any unexpected failure or unexpected pass of a strict expected-failure check makes
the command fail. Only the exact observed status raises `KnownBaselineDefect`; other
errors fail normally. Pytest assertion expansion is disabled so generated Authorization
and HMAC headers cannot appear in expanded assertion diagnostics. Known defects must
be separately approved for remediation. A test
expecting current behavior (for example, logout leaving an access token usable) is
a characterization, not a recommendation to preserve that weakness forever.

Scope stops at P0: no Keycloak integration, issuer mapping, mTLS, production network
changes, role-policy edits, or new authentication implementation. This harness does
not launch or verify Grafana/Loki, the frontend, or production data.

The test data, database lifecycle and DNS fixtures are reproducible. Existing image
tags and transitive Python dependencies are not fully locked by the production build;
resolved versions/image IDs are recorded per run. Future upstream drift can therefore
require a reviewed rebaseline. No dependency upgrade or production build change is
introduced by P0.
