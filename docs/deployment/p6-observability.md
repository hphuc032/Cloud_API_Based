# P6 deployment, validation and rollback

Use approved P5 `9ebca60bff2947e26b2a91ef0273118d21fd6c05` and reviewed P6 changes. Work only on disposable projects until the acceptance report permits otherwise. Use the existing secrets/PKI procedures; never supply credentials on a logged command line. P6 cannot repair the Agent's platform DNS by overriding application validation.

Compose order: `docker/docker-compose.yml`, `docker/p4-compose.yml`, `docker/p5-compose.yml`, `docker/p6-compose.yml`, then a reviewed collector manifest. Set the existing exact HTTPS issuer/origins, secrets, PKI and built SPA paths. P6 must use new project-scoped `p6_loki_data` and `p6_grafana_data` volumes; it never changes an existing Loki schema/volume in place.

Start application/identity services and Kong first. Inspect their container IDs/LogPath using an authorized Docker operator. Generate a Compose overlay mounting only the selected backend/Kong/Keycloak container directories read-only under `/var/log/project/<container-id>`. `P6_PROJECT_LOG_DIR` is an otherwise empty directory with matching empty child mountpoints. Do not mount `/var/lib/docker`, `/`, a Docker socket or unrelated projects. Start Loki, Grafana, then Alloy. The automated P6 runner builds that manifest for its own random project and cleans only its own volumes.

```sh
# Config validation, no production volumes:
docker run --rm -v "$PWD/monitoring/alloy:/etc/alloy:ro" grafana/alloy:v1.14.1 validate /etc/alloy/config.alloy
python3 tests/p6/run.py --focus hardening
python3 tests/p6/run.py
# Legacy regression is isolated and keeps the historical Promtail deployment:
python3 tests/p3/run.py
```

On this vfs cloud host the same reviewed P5 dependency/source overrides can be used. Record actual images and source hashes. API/tests use `cloud-api-tests-flat:verified` for PostgreSQL/TLS client compatibility; later namespace/browser probes may use the smaller verified backend base. No assertion is weakened for an alternate OpenSSL build.

## Pipeline operations

Alloy1.14.1 is digest-pinned. The P6 Kong overlay loads the tracked `p6-telemetry` OSS log-phase plugin and a128KiB OpenResty error ring; raw proxy errors remain disabled and only constant TLS reasons are persisted. Existing Loki2.9.8/Grafana10.4.2 versions are retained for bounded compatibility testing; their age/support status requires review before production. A tested version pin is not proof of ongoing vulnerability support. No commercial feature is used. Alloy readiness is internal `:12345/-/ready`; component errors must also be inspected, since process readiness alone does not prove ingestion. Loki readiness is internal `:3100/ready`, Grafana `:3000/api/health`. Loki and Alloy have no host port; Grafana inherits loopback-only port3001. Authentication is enabled and anonymous signup disabled; verified HTTPS management ingress is required for remote use.

Alloy persists file positions and batches256KiB/1second, with10second request timeout and bounded retry backoff500ms–5s ×10. There is no durable remote-write WAL guarantee here. Prolonged outages, rotated source logs, positions loss, container recreation, disk full or exhausted retries can lose logs. Position replay and Loki deduplication behavior require actual restart testing. Refresh the mount manifest after recreation. No exactly-once delivery claim is made.

Loki retains filesystem chunks/index on a new named volume, single replica/in-memory ring, schema v11 boltdb-shipper24hour index. Target retention168hours (physical deletion validation is currently BLOCKED; do not claim enforced retention), compactor1minute, physical delete delay2hours, two workers. Ingestion2MiB/s, burst4MiB, max query1000series/5000entries. Docker source files10MiB×3 provide a hard local source bound; Loki volume itself has no hard filesystem quota. Monitor host capacity separately; no storage exporter or measured storage alert is implemented. Query limits are not disk limits. Backup filesystem/index consistently during a controlled stop and rehearse restore on an isolated clone; production backup/restore is not certified by configuration alone.

## Migration comparison and rollback

Historical Promtail files are preserved unchanged. Legacy runner supplies comparison of the previous Docker ingestion path. Do not claim equivalent event coverage until both executed results are present. Active P6 excludes Promtail with a rollback-only Compose profile; Alloy alone must be the tested active collector.

If collection fails, stop candidate traffic or restore the approved P5 deployment against its original, separately preserved observability volumes. Preserve P6 Loki and positions for investigation. Do not run two collectors to the same destination without duplicate analysis. Re-enable historical Promtail only through its reviewed original configuration/project boundary. P6 audit rows use the existing schema; no schema downgrade is needed. Deploying P5 does not automatically revoke P6 audit INSERT/sequence grants: run the approved P5 migration job to reapply its original runtime grants while application traffic is stopped. Audit data remains retained for authorized operator access. Never delete production volumes as rollback.

## Transfer (Workspace B only)

P6 is committed locally and exported as a verified Git bundle. See the external manifest for exact commit/tree/SHA256. Workspace A does not push or change account credentials.

```sh
git switch migration/cloud-api-security
git fetch origin
git bundle verify /path/cloud-api-p6.bundle
git fetch /path/cloud-api-p6.bundle migration/cloud-api-security
git merge-base --is-ancestor HEAD FETCH_HEAD
git merge --ff-only FETCH_HEAD
# Separately authorized Workspace B publication:
git push origin migration/cloud-api-security
```

If remote/local ancestry diverges, stop for review; never force-push or rewrite P0–P5.

The operator helper `python3 docker/render_collector.py --project PROJECT --mount-root EMPTY_DIRECTORY --output collector.json` validates exact Compose project membership, one instance of each selected service and the Docker json-file path shape before generating mounts. This helper runs on the authorized host; Alloy itself receives no Docker API access. Public provisioning directories need0755 and public configuration files0644 for nonroot images; secrets/private key modes are unchanged. Alloy runs with a read-only root, all capabilities dropped and no-new-privileges, with only its positions volume and temporary memory filesystem writable.

Final recovery command: `python3 tests/p6/run.py --focus telemetry`. This focused acceptance recovery includes P6 telemetry/lifecycle, the full110-case P5 API suite,145-case active OIDC/P2/P1 pytest suite, original P2 TLS host tests, network/privilege checks and actual transport-reason Loki queries. It does not substitute for the separately recorded browser/identity/rotation and legacy phases. `python3 tests/p6/retention.py` is a mandatory failing storage experiment until physical expiry is independently confirmed. No failing test is skipped or disabled.
