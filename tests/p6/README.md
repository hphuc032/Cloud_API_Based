# P6 disposable validation

`python3 tests/p6/run.py --focus hardening` builds the real P4/P5 candidate with P6 instrumentation and fresh application/identity/log volumes. It supplies its own credentials, PKI, OIDC fixtures and narrow container-directory mounts. It runs P6 ingestion/provisioning checks plus P5 hardening; full mode additionally runs active regression, host checks, browser and key rotation. Legacy P0–P3 uses the independent `tests/p3/run.py` path. DNS failures remain visible.

Use Docker Compose v2 with reset/override support, backend Python dependencies and frontend browser dependencies as documented by P5. Local vfs overrides are inherited from P5; source hashes must match. Raw artifacts are ignored because they can contain generated secrets. Publish only reviewed sanitized evidence. Config validation is necessary but insufficient: tests query actual Loki, not fabricated dashboard numbers.

`--focus telemetry` performs clean recovery plus full P5/API regressions, P2 TLS/network checks and sanitized transport ingestion. It uses a custom OSS log-phase plugin without changing JWT or TLS policy. `python3 tests/p6/retention.py` separately tests physical expiry on a new storage project; current failure blocks acceptance. See the report for exact failure and unexecuted checks.
