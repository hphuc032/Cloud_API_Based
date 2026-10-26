# Part A — Upgrade and rollback gates

2026-10-26. **Procedure only; upgrade and rollback NOT EXECUTED.** Neither candidate
was activated. The approved source/configuration, existing user services and all
application/storage volumes remain unchanged. There is no Part A operational
change to undo. Removing an inactive downloaded image would not resolve a release
blocker and was not performed.

## Prerequisites

1. Qualify exact OSS Kong crypto and Loki Go/gRPC/HTTP2 artifacts; inspect actual
   binaries and scan immutable linux/amd64 images with current advisory metadata.
2. Establish adequate host physical RAM and disk headroom for a **fresh isolated**
   baseline. Never stop user services, prune globally or reset WSL for capacity.
3. Use a native WSL clean source snapshot and unique Compose project with dedicated
   volumes, generated test credentials and test PKI. Confirm resource ownership
   from labels before any cleanup. Never attach a production or user database.
4. Follow the [full regression matrix](../testing/part-a-regression-results.md).
   All commands there under continuation are proposals, not executed acceptance.

## Kong

The operational baseline remains Kong 3.9.3 descriptor
`sha256:92035d16d7ff86b7bc12fb1d0090d29357d924238b1880f78735f3f2fea6b631`.
3.9.4 descriptor
`sha256:aa4a4687b1330e427ad0d3b27a0606b833894297c78abf1a212edc9ba73c8620`
was inspected and rejected as the crypto remedy. Do not deploy it on the strength
of this document. DB-less configuration means no Kong database migration is
expected; application and identity databases must remain untouched.

For a later qualified candidate, archive the matching declarative input, generated
JWT credentials, key/CA enrollment, limiter and telemetry Lua modules, filesystem
UID/modes, trusted forwarding configuration and `/run/kong` prefix behavior.
Keep generated secrets in private runtime storage, not Git. Validate config and
startup in the disposable environment before changing its gateway image. Run
good/negative certificates, 16 TLS methods per applicable mode, JWT/claims,
RBAC/BOLA, rates/recovery, rotation/outage, browser and logging tests.

On failure, recreate **only that disposable gateway** with its original digest
and matching configuration/secret enrollment. Restore trust as a coordinated set;
do not restore an expired/revoked key or weaken verification. Re-run the same
controls. A rollback recovering traffic does not remove the old lifecycle issue.

## Loki

Baseline Loki 2.9.17 descriptor
`sha256:c4a25af6f2709fa625d88ee5df494a332a85f30e9575854031667823ecc5be04`
and `monitoring/loki/p6-loki.yml` remain active repository choices. The inspected
3.7.8 descriptor
`sha256:1107dd5274e0ada47e42472b7a7e71f3b2a2fe878878108f3e2f9e51528f0193`
is unqualified. Its removed `shared_store` fields, explicit delete store and
healthcheck-tool compatibility require a reviewed target fixture before use.

1. Populate a dedicated baseline test volume with distinguishable historical,
   expired and current logs; verify queries and collector positions.
2. Quiesce only that test Loki instance. Make an exact cold copy, preserve owner/
   permissions, inventory every object and record byte SHA256 hashes.
3. Start a qualified candidate against a **second copy**, never the only copy.
   Preserve historical schema periods and 168-hour production retention; any
   accelerated expiry fixture must remain isolated from production configuration.
4. Verify old-data queries, new ingestion, restart consistency, compactor progress,
   logical retention and actual physical removal of expired objects. Prove hashes
   of retained objects remain unchanged, rather than accepting query absence alone.
5. Verify Alloy positions/recreate recovery, gateway/backend/Keycloak event
   correlation, datasource/dashboards, all six alert transitions and redaction.
   Publish no Loki host port; retain observability membership and RPC requirements.
6. Roll back to the original image **and original configuration plus untouched
   pre-upgrade cold copy**. Restore the matching disposable collector state and
   verify old/current queries and fresh ingestion. Data written only to the
   candidate copy requires an explicit recovery policy; it is not automatically
   present in the cold snapshot.

Do not run 2.9.17 against storage transformed by a later version or claim supported
in-place downgrade. Do not rewrite v11 history into v13 merely to pass startup.
Do not disable compaction, physical deletion, readiness or security checks.

Inventory, copy hashes, timings, query results and recovery exits must be recorded
before claiming rollback PASS. No such backup/upgrade/rollback was attempted in
Part A, and no production recovery capability was newly established.
