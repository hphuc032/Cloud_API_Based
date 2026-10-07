# P1 execution and acceptance record

Completed 2026-10-08 (Asia/Saigon) on `migration/cloud-api-security`, based on approved
P0 commit `0bc7a404e4a1d5a4d74a82293dbe9dc857a7a030`. See
[deployment architecture, network/role matrices, operations and rollback](../deployment/p1-deployment.md).
The P1 commit is identified in the completion message (`git log -1 --format=%H`).

## Final results

Final isolated project: `cloud-api-p1-e3110176befa`.
Run: 2026-10-08 05:49:20–05:51:30 Asia/Saigon
(2026-10-07 22:49:20–22:51:30 UTC). Exit code 0; cleanup completed.

| Group | Tests | Pass | Expected failure | Unexpected failure/error |
|---|---:|---:|---:|---:|
| P0 auth/login/JWT/refresh/logout | 21 | 19 | 2 | 0 |
| P0 Product/Order/User/RBAC/ownership | 22 | 20 | 2 | 0 |
| P0 migrations/template/backup-restore | 3 | 3 | 0 | 0 |
| P0 live Kong rate limiting | 1 | 1 | 0 | 0 |
| P0 webhook and SSRF | 42 | 39 | 3 | 0 |
| P1 PostgreSQL privilege checks | 18 | 18 | 0 | 0 |
| P1 existing-database adoption | 1 | 1 | 0 | 0 |
| P1 host/container integration checks | 16 | 16 | 0 | 0 |
| **Total** | **124** | **117** | **7** | **0** |

Pytest: 108 collected, **101 passed / 7 xfailed**, 25.63 seconds. Host unittest:
**16 passed**, 61.334 seconds. The two existing dependency deprecation warnings
(Starlette/AnyIO alias and Passlib `crypt`) remain.

**P0 comparison:** approved P0 was 82 passed + 7 expected failures; under P1 it remains
exactly 82 passed + 7 expected failures. The seven defect test functions/decorators
were compared by AST against P0 and are unchanged. No defect was fixed or converted
to a pass. Application auth/routes/models, initial migration and Kong declaration
have no diff from P0. Test-administrator fixtures were separated from runtime fixtures:
DB creation, cleanup and backups use a dedicated test-admin DSN; application requests
and ordinary fixtures use the limited runtime role. Assertions/business expectations
were not relaxed and runtime was not granted TRUNCATE/DDL for test convenience.

## P1 evidence

- Actual production Compose definition was built and started with an overlay removing
  UI/proxy host ports only and adding the test runner. Fresh database volume, secrets,
  Keycloak, Kong, API and monitoring services were exercised, not just static YAML.
- PostgreSQL has no published port in either actual inspection or the base Compose
  model. Every production service has exactly its documented network memberships.
- Probes share each actual service's network namespace. Backend reached PostgreSQL
  by DNS and real container IP; Kong, Keycloak, Loki, Promtail and Grafana failed both
  connection attempts. No probe was attached to an extra network to force success.
- Bootstrap and migration jobs exited 0 before backend startup; migration used
  `app_migrator`. Restarting backend did not rerun or replace the migration job.
- Runtime role attributes are non-superuser, no CREATEDB/CREATEROLE/replication/BYPASSRLS;
  it owns no public-schema objects and lacks database CREATE/TEMP and schema CREATE.
- Fourteen real SQL denials cover table CREATE/ALTER/DROP, schema CREATE, TEMP table
  CREATE, function CREATE, self-escalation, SET ROLE to migrator/postgres, TRUNCATE,
  physical product DELETE, Alembic-version writes, audit-log reads and category INSERT.
- Required runtime INSERT/SELECT/UPDATE, UUID defaults, enum values, timestamp triggers
  and FK-linked records work. The full P0 suite exercises the same permissions through
  application endpoints. Soft product deletion and order status semantics are preserved.
- Migration owns application objects and can CREATE/ALTER/DROP its own probe table.
  A synthetic database created with the unchanged P0 migration as postgres was seeded,
  adopted and migrated twice. Seeded data, UUIDs and user/product/order/item relationships
  were byte-for-byte equal in row snapshots and readable through app_runtime afterward.
- Runtime and migration passwords include reserved URL characters in the test run.
  Startup, Alembic configuration and real database authentication succeeded with them.
- `/health/ready` returned 503 during a DB outage in three probes, each under five
  seconds including CLI overhead; `/health` remained 200. Readiness recovered after
  PostgreSQL restart, and an incorrect Alembic head produced 503 until restored.
- Secret mount assignments and inspectable container configuration were checked;
  no generated secret value was present in container Config. Saved image layers for
  backend/bootstrap/migration/test images were scanned for every generated runtime
  secret, including compressed layers. None were found. Backend image source contained
  neither `.env` nor `.secrets`. Temporary image archives were removed after inspection.
- No service mounts Docker's socket or runs privileged. Promtail readiness, Grafana
  health and actual backend log ingestion into Loki passed after the collector change.
- All test project containers/networks/volumes and temporary secret files were removed.
  The unrelated existing `nginx`, `backend`, and `Duck-nettool` containers stayed running.

## Iterations and resolved blockers

Three full P1 runner invocations occurred; earlier failures were not hidden:

1. Project `cloud-api-p1-35b1f4c324a3`: 100 pytest passes + 7 expected failures;
   13/16 host checks passed. The all-internal API network blocked public DNS. The
   test-only tmpfs database also lost its schema on stop/start, causing two readiness
   failures. The overlay was corrected to use the real project-scoped deployment
   volume, which is deleted only during final cleanup.
2. The user explicitly approved a standard API bridge to preserve DNS/egress, keeping
   the application data network internal. Project `cloud-api-p1-cb3efa977d06`:
   101 pytest passes + 7 expected failures; 15/16 host checks passed. An outage probe
   timed out before receiving readiness. A bounded single-worker readiness wait was
   added so DNS/socket stalls cannot indefinitely delay the HTTP result or accumulate
   readiness jobs. Authentication/business endpoints were unchanged.
3. Project `cloud-api-p1-e3110176befa`: final result above, all gates passed.

## Commands executed

At repository root, PowerShell; Git commands used the command-local option
`-c safe.directory=D:/MatMaHoc/Project_CLOUD_API` because of the execution identity.

```text
git status --short
git log -1 --format="%H %s"
git branch --show-current
docker version --format "{{.Server.Version}}"
python tests/p1/run.py                  # three complete invocations
git diff --check
git diff --stat
git diff --exit-code 0bc7a404e4a1d5a4d74a82293dbe9dc857a7a030 -- backend/app/auth backend/app/routes backend/app/models backend/alembic/versions gateway/kong.yml
docker ps --format "{{.Names}} {{.Status}}"
```

Each runner invokes, with its unique project, OS null env-file, actual Compose file
and P1 test overlay:

```text
python docker/generate_secrets.py --new-deployment --directory <temporary secret directory>
docker compose ... build
docker compose ... up -d --wait --wait-timeout 300 backend kong keycloak grafana promtail
docker compose ... ps -a -q
docker inspect <project containers>
docker compose ... run --rm --no-deps -T tests
docker compose ... down --volumes --remove-orphans --timeout 10
```

Container test command: `python /tests/p1/launch.py`, which configures file-supplied
runtime/admin/migration DSNs then invokes the complete P0 pytest suite plus the two
P1 pytest modules. These execute real Alembic upgrades/downgrades, pg_dump/pg_restore,
bootstrap/migration jobs and SQL probes. Host checks execute `docker network inspect`,
`docker run --rm --network container:<id> --entrypoint python <probe-image> -c <probe>`,
`docker image save`, Compose `exec`, `stop/start postgres` and `restart backend`.
No secret values are supplied as command literals.

Static checks parsed all new Python sources, compared all seven defect tests with P0,
verified the unchanged authentication/business/migration/Kong files and checked Git
whitespace. Final staging includes only the P1 source/test/documentation paths and
excludes generated artifacts, keys, secrets and pre-existing binary documents.

## Files created and modified

Created:

- `.gitattributes` (Linux shell LF preservation).
- `backend/app/readiness.py`.
- `backend/deployment/__init__.py`, `common.py`, `bootstrap.py`, `migrate.py`, `serve.py`.
- `docker/generate_secrets.py`, `docker/keycloak-entrypoint.sh`.
- `docs/deployment/p1-deployment.md`, `docs/testing/p1-results.md`.
- `tests/p1/Dockerfile`, `Dockerfile.dockerignore`, `README.md`, `compose.yml`, `launch.py`,
  `run.py`, `host_checks.py`, `test_privileges.py`, `test_adoption.py`.

Modified:

- `.gitignore`, `README.md`, `backend/.dockerignore`.
- `backend/alembic/env.py` (URL percent escaping; initial migration unchanged).
- `backend/app/database/session.py` (connection/pool timeout bounds), `backend/main.py`
  (new readiness route; existing health and business routes unchanged).
- `docker/.env.example`, `docker/docker-compose.yml`.
- `monitoring/promtail/promtail-config.yml`.
- `tests/p0/conftest.py`, `tests/p0/test_database.py` (test-admin/runtime separation).

## Remaining limitations and phase boundary

API transport retains outbound egress by explicit approval. Network membership is
reachability isolation, not encryption, mutual authentication or a directional/full
firewall. Host/Docker administration remains trusted. Single-node file secrets need
filesystem protection and coordinated rotation. Log-file mounts expose log/metadata
content to the collector; they remove Docker API control but do not fully sandbox it.
Images/transitive dependencies are not fully pinned or upgraded by this phase.

Compose startup/health ordering is not HA or continuous traffic removal. Keycloak is
still independent `start-dev` with embedded storage. Kong still only provides its prior
gateway/rate-limit behavior. Local JWT issuance/algorithm and all seven P0 defects are
unchanged. Frontend browser flows, real production datasets, concurrent refresh/stock
races, sustained load, cloud firewall controls and production disaster recovery are
not certified by these isolated tests. No HTTPS/mTLS, OIDC/JWT gateway plugin,
Kubernetes or new identity datastore is introduced. Stop after P1; P2 requires review.
