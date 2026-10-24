# P7 backup, recovery and rollback

The executable drill is `tests/p7/recovery.py`, invoked by the guarded random
Compose P7 runner. It is authorized only for disposable synthetic data. Never
run it against existing application or production volumes.

## Paired database recovery drill

1. Seed four real Keycloak identities and explicit reviewed application mappings,
   two customer-owned orders, products, audit records and a webhook receipt.
2. Preserve monitoring volumes/positions and temporarily remove only this lab's
   Grafana/Alloy containers to bound Docker vfs disk use; this creates a documented
   collection gap during the restore, not a lossless monitoring guarantee. Start two new PostgreSQL instances on a new internal recovery network, fresh
   volumes, no host ports. Stop FastAPI and Keycloak to quiesce both writers.
3. Export each cluster's role attributes/verifiers and a custom-format `pg_dump
   --create` archive; stream them directly in memory to the new instances with
   `psql ON_ERROR_STOP` and `pg_restore --create --exit-on-error`. Generated role
   verifiers and dumps never enter tracked artifacts or shell argument values.
   The fresh instances already have postgres, so exclude only its CREATE ROLE
   statement; retain its attributes. This is not a generic production role merger.
4. Compare every public table's count and sorted row digest, FK/constraint
   definitions and table owners. Explicitly check mappings/ownership and runtime
   SELECT-only mappings, INSERT-only audit, no public schema CREATE.
5. Stop original DB containers, keep original volumes untouched. Add the existing
   private service DNS aliases to the recovered instances on the corresponding
   lab data networks. Restart the same TLS/OIDC application services.
6. Obtain fresh actual code+PKCE tokens from the recovered IdP for all four users.
   Assert stable application UUIDs/roles, both order owners, customer BOLA denial
   and admin-only user listing via Kong HTTPS and backend mTLS.
7. Force-recreate backend and repeat those assertions. Stop writers, detach recovery
   aliases, restart original databases and repeat authenticated checks. Finally
   clean only fresh recovery instances. Refresh Alloy's narrow log mounts for the
   recreated backend ID, recreate Grafana with its existing lab volume and query dashboards/rules/new log ingestion.

See [actual P7 results](../testing/p7-results.md) and machine-readable recovery
records for what passed or failed. An initial failed seed/restore attempt remains
in evidence. An archived hash is not substituted for an authenticated restore test.
This consistency point assumes these stopped writers are the only writers;
external production integrations must also be quiesced. There is no distributed
transaction or continuous replication. No RPO/RTO or disaster/HA guarantee is made.

## Recovery material and scope

Application data includes users, orders/items, mappings, receipts and audit logs.
Identity backup contains credentials and signing keys. Real backups require
restricted/encrypted storage, tested key access, integrity manifests, off-host
copies, retention and operator-controlled deletion; none belongs in Git.
Separately retain TLS issuers/enrollment, runtime secrets, exact issuer/origins,
reviewed account manifests, Git commit/tree, image digests and Compose project IDs.
Never generate replacement secrets incidentally during restore.

Dashboards, rules, Alloy and Loki configuration are versioned nonsecret Git files.
P6 and P7 restart evidence covers persistent Loki observations and Grafana
provisioning. It does **not** prove cold backup/restore of Loki chunks/indexes,
Grafana SQLite/custom UI edits, Alloy positions or production two-hour retention
timing. Those remain NOT EXECUTED. A cold storage backup requires coordinated
shutdown, version-compatible full volume copies including indexes/markers and
positions, fresh-volume restore and independent queries; do not copy a live
SQLite/index tree and call it consistent. External alert delivery is not configured.

## Release rollback boundaries

P7 changes tests/docs only; application, schema, identity and telemetry policy
remain P6. A P7-to-approved-P6 application/configuration rollback needs no schema
or grant downgrade, no issuer/key change and no data deletion. The drill's return
to original databases is a tested data-routing rehearsal; deployment of historical
P6 binaries from a clean release directory is operator-reviewed, NOT EXECUTED.

Retain OIDC candidate isolation. Do not add automatic legacy fallback, assume
Keycloak-only users have local passwords, replace identity mappings, delete audit
history or drop receipts. P6-to-P5 changes collector/audit grants and requires the
[P6 procedure](p6-observability.md); P5-to-P4 requires receipt backup and a reviewed
0003→0002 downgrade with matching readiness and replay risk review. Those security
downgrades are NOT EXECUTED here. P4-to-legacy requires separate explicit approval
and known-password handling; it is not a safe response to an IdP outage. Preserve
CA/key continuity and prior dashboard/alert revisions during any reviewed rollback.
