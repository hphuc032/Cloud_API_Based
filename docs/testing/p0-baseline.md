# P0 baseline evidence and review record

Date: 2026-10-07. Branch: `migration/cloud-api-security`.
Starting commit: `fbb1016ae64efa98197ffbc514d13a8433dc1bb2`.
Author identity: `Nguyen Hoang Phuc <nhpntd@gmail.com>`.
Scope: P0 only. The P0 commit hash is provided in the completion message and can be
obtained with `git log -1 --format=%H`; a commit cannot contain its own final hash.

## Result

The final executed suite collected **89 tests: 82 passed, 7 expected failures,
0 unexpected failures, 0 unexpected passes**. Pytest exited 0. Expected failures
are confirmed existing defects, not passing security controls. Two dependency
deprecation warnings remain (Starlette's AnyIO alias and Passlib's `crypt` import).

Final run: `cloud-api-p0-aa010f69c183`, 2026-10-07 15:10:18–15:11:19 UTC
(22:10:18–22:11:19 Asia/Saigon); pytest duration 28.92 seconds.
An earlier run had 80 passed / 5 expected failures in 33.98 seconds. The final run
adds exact-defect classification, two order-status characterization cases, and two
explicit-null defect checks. No application defect was fixed between runs.

All test containers and the test network were removed successfully. The existing
`nginx`, `backend`, and `Duck-nettool` containers remained running. No production
database, volume, deployment configuration, authentication code, or business policy
was modified.

## Pass/fail matrix

| Area | Passed | Existing failures | Evidence |
|---|---:|---:|---|
| JWT/login/registration/refresh/logout | 19 | 2 | Missing/garbage/wrong-key/expired/wrong-type/no-sub/unknown-user JWTs; real role-specific login; expiry claims; hashed refresh persistence; rotation/reuse; expired/revoked/unknown/disabled refresh; logout ownership; forced customer registration; lockout |
| Product/Order/User authorization | 20 | 2 | Anonymous/customer/staff/admin CRUD matrix; order owner forced server-side; exact list visibility; cross-customer order rejection; status permissions; user self/admin checks; database role/is_active authority; stock and totals; current status transitions |
| Alembic and backup/restore | 3 | 0 | Empty DB upgrade/idempotence/downgrade/re-upgrade; executable template-generated revision in temp copy; real pg_dump/pg_restore preserving data/UUIDs/FKs |
| Live Kong | 1 | 0 | Existing declaration forwards to Uvicorn, enforces 60 requests/minute, returns 429 and Retry-After, shares caller quota across routes; direct backend remains healthy |
| Webhook and SSRF | 39 | 3 | Correct HMAC; missing/invalid/tampered signatures/body/timestamp; exact ±300-second boundaries; invalid JSON; DEBUG helper disabled; role gate; allowlist/subdomain boundaries; private/loopback/link-local IPv4/IPv6; mixed DNS answers and DNS failure |
| **Total** | **82** | **7** | **89 executed; no unexpected failures** |

Current authorization policy was characterized, not redesigned:

| Operation | Anonymous | Customer | Staff | Admin |
|---|---|---|---|---|
| Product list/read | 200 | 200 | 200 | 200 |
| Product create/update/delete | 401 | 403 | Allowed | Allowed |
| Order create | 401 | Allowed | Allowed | Allowed |
| Order list | 401 | Own only | All | All |
| Read Customer B's order as Customer A / elevated role | 401 | 403 | 200 | 200 |
| Order status update | 401 | 403 | Allowed | Allowed |
| User self read | 401 | 200 | 200 | 200 |
| Other user read / user list / user update | 401 | 403 | 403 | Allowed |
| SSRF validation endpoint | 401 | 403 | Allowed | Allowed |

## Existing defects, left unchanged

Each listed defect is executed as a strict expected failure. Only its observed HTTP
status qualifies; any unrelated bad outcome fails the suite. An unexpected fix also
fails as XPASS until the baseline is reviewed. Desired statuses are test signals for
future remediation review, not authorization to change policy during P0.

| ID | Reproducer and observed behavior | Required review |
|---|---|---|
| P0-D01 | Correctly signed current access JWT with a valid user `sub` and `type=access`, but no `exp`, returns 200 on `/auth/me` | Require expiry during future token hardening. This requires a signer-issued token; it is not a demonstrated signature forgery. |
| P0-D02 | Correctly signed access JWT with non-UUID `sub` returns 500 | Validate subject before database UUID comparison; test anticipates 401. |
| P0-D03 | Validly signed webhook containing `[]` returns 500 | Validate JSON object/event schema; test anticipates 400. |
| P0-D04 | Identical valid webhook submitted twice within the allowed time window returns 200 twice | Agree event identity and idempotency/replay policy. The test uses 409 as a proposed rejection signal; an idempotent 2xx contract needs a different assertion. |
| P0-D05 | Allowlisted domain resolving to `::ffff:127.0.0.1` is accepted (200) | Normalize IPv4-mapped IPv6 before checking address policy. The current endpoint only validates URLs; this does not demonstrate an actual internal HTTP fetch. |
| P0-D06 | Staff PATCH product with `{"price": null}` returns 500 | Reject null for required persisted fields; test anticipates 422. |
| P0-D07 | Admin PATCH another user's role with `{"role": null}` returns 500 | Reject null for required persisted fields; test anticipates 422. |

Additional current behavior is deliberately recorded as passing characterization:
logout revokes only an owned refresh token and leaves the access JWT usable; replay
of a rotated refresh token gets 401 but does not revoke its replacement; staff/admin
may create orders; staff/admin may assign any order-status enum, including backwards
transitions; database roles and active flags take effect despite old token claims.
These tests must not be interpreted as approval of a new business policy.

## Reproducibility blocker repaired

`backend/alembic/script.py.mako` was an empty tracked file. It now has the standard
revision metadata/imports/upgrade/downgrade template. The test generates a revision
only in a temporary directory, executes its upgrade against an empty disposable DB,
checks the revision stamp, and executes downgrade. No new production schema revision
was created; existing migration contents and schema behavior are unchanged.

## Database evidence

Schema creation uses only the existing Alembic initial revision, never `create_all`
or `backend/database/schema.sql`. Tests verify seven application tables plus
`alembic_version`, seven foreign keys, four update triggers and the user-role enum.
They also downgrade to base and rebuild successfully.

The backup test uses PostgreSQL 16 `pg_dump -Fc` and `pg_restore --exit-on-error`
against a second freshly created database. Every row in all seven application tables
and the Alembic version is compared before/after. Populated fixtures include four
users, one product, two orders with their items and one hashed refresh token;
categories/audit logs are empty in this fixture. UUIDs, roles, account flags, token
hashes, values, timestamps and user/order/product links are preserved. The restored
database still has seven FK constraints and accepts `alembic upgrade head` without
changing the snapshot. Dumps never leave the disposable test container.

## Commands executed

Run from `D:\MatMaHoc\Project_CLOUD_API` (PowerShell). Command-local safe.directory
was needed because the execution identity differs from the checkout owner; no global
Git trust configuration was changed.

```powershell
git -c safe.directory=D:/MatMaHoc/Project_CLOUD_API switch -c migration/cloud-api-security
docker pull postgres:16-bookworm
docker pull kong:3.8
python tests/p0/run.py
python tests/p0/run.py
git -c safe.directory=D:/MatMaHoc/Project_CLOUD_API diff --check
git -c safe.directory=D:/MatMaHoc/Project_CLOUD_API diff --stat
docker ps --format '{{.Names}}'
```

The runner executed the following for each unique project (`<compose>` means
`docker compose --env-file <OS null device> -p <random project> -f tests/p0/compose.yml`):

```text
<compose> build
<compose> up -d --wait --wait-timeout 180 postgres backend kong
<compose> images --format json
<compose> exec -T backend pip freeze                    # final run
<compose> run --rm --no-deps -T tests pip freeze         # final run
<compose> run --rm -T tests
<compose> down --volumes --remove-orphans --timeout 10
```

Test-container command:

```text
pytest -c /tests/pytest.ini /tests --tb=short -ra --junitxml=/results/junit.xml
```

The tests additionally executed `alembic upgrade head`, `alembic downgrade base`,
`alembic revision -m "p0 template probe" --rev-id p0_template_probe` in a temporary
copy, `pg_dump -h postgres -U postgres -d p0_baseline -Fc -f <temporary dump>`, and
`pg_restore -h postgres -U postgres -d <isolated DB> --exit-on-error <temporary dump>`.
Passwords were passed through ephemeral environment, never command literals.

Commit preparation uses explicit paths (`.gitignore`, the migration template,
`tests/p0`, and this report), `git diff --cached --check`, and commit message
`test: establish P0 security migration baseline`. Unrelated pre-existing binary
documents remain untracked and are excluded. No push is part of this phase.

## Environment and limitations

Executed with Docker Desktop 4.73.1 / Engine 29.4.3, Compose v5.1.3, Linux amd64,
test-runner Python 3.11.2, pytest 8.2.0, FastAPI 0.111.0, SQLAlchemy 2.0.30,
Alembic 1.13.1, PostgreSQL 16 and Kong OSS 3.8.

Resolved image digests:

- PostgreSQL: `sha256:0ea6700a3b4f0ae6ce746519073558aed4d88a79d8d07622a9a644946c7319c4`.
- Kong: `sha256:8635e3c97b27cf71ed620bb30f6091dbab1d39aad99a6c54dd9c3cfccb6d1013`.
- Backend build's Python base: `sha256:0dd364ba7e10242f07755449e3a3d0e35f9efd987952737b90def6709ab0c5ce`.

Local ignored evidence: `tests/p0/artifacts/{pytest.txt,junit.xml,images.json,run.json,
backend-packages.txt,tests-packages.txt}`. Both final resolved Python package lists
matched. Top-level dependency pins are unchanged; transitive dependencies and image
tags are not fully locked, so rebuilding at a later date can expose upstream drift.
Package/image manifests record the environment actually tested.

No requested P0 category was blocked by the environment. The following are outside
what this execution establishes:

- Frontend browser workflows and Grafana/Loki ingestion/alerts were not exercised;
  the P0 harness contains backend, PostgreSQL and Kong only. Their source/configuration
  is unchanged. API testing does not certify their end-to-end operation.
- SSRF tests verify current URL/DNS validation with deterministic DNS answers; the
  current route performs no outbound fetch. DNS rebinding, redirects and egress
  filtering are not verified by these tests.
- Kong limiting is checked for one caller/IP, one node and one quota window. Window
  recovery, load behavior, spoofing/proxy-chain configurations, failover and distributed
  counters were not tested. The direct backend probe occurs only inside the test network.
- Refresh rotation is verified sequentially; concurrent refresh races, concurrent
  stock updates/overselling, sustained load and transaction-race resistance are not tested.
- Backup/restore uses synthetic isolated data, not production data, filesystem volume
  recovery, encrypted off-host backups, point-in-time recovery, RPO/RTO or disaster drills.
- No Keycloak, issuer/subject mapping, strict issuer/audience migration, HTTPS/mTLS,
  production network segmentation, Kubernetes or dependency upgrades were introduced.

## Files and rollback

Modified: `.gitignore` (ignore P0 outputs), `backend/alembic/script.py.mako` (template).
Added: this report; `tests/p0/README.md`, `run.py`, `compose.yml`, `Dockerfile`,
`Dockerfile.dockerignore`, `pytest.ini`, `conftest.py`, `baseline.py`, `test_auth.py`,
`test_authorization.py`, `test_database.py`, `test_gateway.py`, `test_webhook_ssrf.py`.

Reverting the P0 commit removes the harness/report and restores the former template;
it does not need an application database rollback because no application migration
was added or run against existing data. Review P0 before authorizing P1.
