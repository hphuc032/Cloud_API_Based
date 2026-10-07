# P1 validation

From the repository root:

```powershell
python tests/p1/run.py
```

The runner uses the actual `docker/docker-compose.yml` plus a test overlay that removes
only host-published UI/proxy ports and adds the test runner. It does not add production
services to networks or weaken database permissions for tests. Each run uses a random
Compose project, project-scoped volumes, temporary secret files and `p0_baseline` DB.
The runner removes only those containers/networks/volumes and temporary secret files.

The full P0 suite retains all 89 cases and all seven strict expected failures. Fixture
cleanup/database creation/dump/restore use a separate test-administrator DSN; FastAPI
requests and normal data fixtures run as the real `app_runtime` role. No authentication
dependency is overridden. This distinction avoids granting DDL/TRUNCATE to runtime
merely to support test fixtures. Running `python tests/p0/run.py` remains supported.

Additional pytest checks cover runtime DML, 14 privilege denials, role attributes,
migration ownership/DDL, reserved characters in password URLs, and adoption of a
synthetic P0 database without changing IDs/linked rows. Host unittest checks inspect
the actual memberships, job startup order, port bindings and secret mounts; probe DNS
and direct IP connectivity inside each actual service's network namespace; inspect
saved image layers for generated runtime secrets; verify log ingestion; and exercise
database outage/recovery, migration-head mismatch and backend restart without migration.
Probe containers share only the target's network namespace; they do not join extra
networks or receive credentials.

Ignored evidence is in `tests/p1/artifacts/`: pytest output, JUnit XML, host-check output
and counts, container metadata and the run summary. Treat artifacts as local operational
evidence, not publishable logs. No actual secrets, database dumps or image archives are
committed. Image archives are temporary and removed after inspection.

The integration tests require working Docker, image/package access on a cold build,
the rootful daemon log path and public DNS for the existing SSRF validation behavior.
They do not test production datasets, concurrent race resistance, a cloud firewall,
TLS/mTLS, failover, OIDC or frontend browser flows. Expected P0 defects remain defects.
