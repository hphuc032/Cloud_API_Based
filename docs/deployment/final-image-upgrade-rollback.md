# Final image upgrade and rollback — 2026-10-25

**Local validation only; release remains BLOCKED.** These procedures preserve data boundaries and require a separately reviewed production change window. Do not run production migrations merely because the lab passed. Never use `down -v`, global prune, old binaries on migrated storage, or private-key permission broadening as rollback.

## Ordered rollout and dependencies

| Order | Change | Dependency / risk | Validation and rollback |
|---|---|---|---|
|1|Same-version nginx slim-derived image|Must include GNU wget with real CA verification; all identity/SPA execution paths must use the same tested artifact|Both browser suites, strict CSP/headers, identity proxy, good/bad CA health. Restore original image/config on separate lab project; no nginx persistent schema.|
|2|Loki2.9.17|Keep v11, boltdb-shipper, filesystem and retention168h; do not silently enable Loki3 schema/storage|Cold-copy stopped old volume before upgrade; query old/new markers and independent physical-retention proof. Roll back old image **and cold pre-upgrade volume**, not an assumed reverse-compatible migrated volume.|
|3|Grafana10.4.19|Provisioning/datasource/six rule semantics and SQLite/dashboard persistence|Stop Grafana; cold-copy owned data volume preserving UID472. Upgrade cloned/isolated storage; validate dashboard/rule queries, alert firing/recovery and new writes. Rollback old image plus pre-upgrade copy.|
|4|Kong OSS3.9.3|DB-less config/schema/plugins/JWKS/crypto compatibility; default image UID changed1000→1001|Keep deployment UID/GID1000 and mode0600 keys. Set `KONG_PREFIX=/run/kong` with owned tmpfs; never mount over packaged `/usr/local/kong/lib`. Parse/reload and verify listener readiness, JWT, mTLS, limiter and log privacy. Revert matching image/config/prefix test expectations together; no Kong DB migration.|
|5|Keycloak26.8.1|Schema migration is irreversible by binary downgrade; app/identity mapping consistency and signing keys must survive|Stop all Keycloak writers and identity PostgreSQL before physical copy. New image migrates only a disposable copy. Real migration152→237, key/ID/policy comparisons, restart and old-image/original-DB rollback were verified. For production, preserve a paired application/identity recovery point and restore both approved installation and pre-upgrade identity DB.|
|6|Alloy1.14.2|Stable component names and `/var/lib/alloy` positions; project log mount manifest must follow recreated source containers|Cold-copy positions while stopped. Validate old offset→new event→new-version restart→old image on cold positions. Preserve read-only scoped mounts, cap_dropALL/no-new-privileges and exact config; no Docker socket. Loki dedup alone is insufficient—read counters prove offsets.|
|7|Backend build pin/runtime pip removal|No auth/business/library version change; privileged jobs still need Alembic/runtime libraries|Hash-locked binary wheels and `pip check` precede uninstall. Verify imports, clean migration/bootstrap, role denial/DML, readiness and full regression. Restore previous built image/source pin in a new commit if needed; app schema unchanged.|

This is the actual staged validation sequence, followed by complete legacy/active regression and scans of final actual IDs. Do not treat the sequence as permission to deploy unaccepted HIGH/CRITICAL risk.

## Tested isolated procedures

`tests/p7/image_upgrade.py` creates its own random internal network and volumes for Loki/Grafana. It seeds old state, stops/cold-copies it, upgrades the original disposable storage, writes new state, then starts the old image against the cold copy. No caller can supply an existing data volume or production project. It records both exact image IDs and cleanup codes.

`tests/p7/alloy_upgrade.py` does the equivalent for file positions using the unchanged production pipeline, scoped fake project logs and a separate Loki. Independent read counters1/1/1/3 demonstrate that the new version/restart do not replay the first line and that old cold positions resume correctly. Its cleanup verifies project labels, including containers created but not started, and refuses foreign resources. The start-failure/ownership-control experiment and final full positions run pass.

`tests/p7/run.py --focus recovery --identity-upgrade-from <official-pinned-old> --identity-upgrade-to <official-pinned-new>` starts only a random P7 test DB, seeds existing reviewed identities, stops old identity writers, validates the owned volume label, copies that cold data to a distinct labelled volume, and migrates only the copy. It compares issuer/realm/client/users/RSA key hashes and application table digests, performs real PKCE/RBAC/ownership, restarts the new pair, then returns to the old image and original identity DB. The new JPA durability flag and SCIM feature flag are removed for the old-version start. Raw database exports/verifiers are never evidence files.

The original full P7 paired recovery is separate: quiesced app/identity backups stream in memory to two fresh PostgreSQL instances; rows, constraints, owners and runtime grants compare; the recovered PKCE→Kong→mTLS→DB chain, backend recreation and return to originals pass. Monitoring peers are recreated and the project-only collector mount manifest is refreshed before current ingestion and rule checks. This is not a production RTO guarantee.

## Keycloak change specifics

Keep PostgreSQL16 and application UUIDs/FKs. Keep `(trusted issuer, subject)→existing users.id` review, DB roles and `is_active` authority. Do not link by email or replace app IDs with subjects.

Upstream26.7 introduces asynchronous ephemeral commit behavior; the deployment sets `KC_SPI_CONNECTIONS_JPA__QUARKUS__ASYNC_COMMIT=false` to preserve prior durability. Upstream26.8 enables a new SCIM surface; `KC_FEATURES_DISABLED=scim-api` disables the unused feature. These are recognized target options, not guessed environment names. Keep PKCE, exact HTTPS redirects/issuer, S256, RS256, refresh rotation and independent FastAPI validation.

Migration notes were reviewed across26.3–26.8, including constraints, session/index changes, realm DISPLAY_NAME promotion and persistent session/expiry data. Downgrading a binary against the migrated DB is unsupported. A rollback requires the old installation and the pre-upgrade DB. See [Keycloak’s upgrade guide](https://www.keycloak.org/docs/26.8.1/upgrading/) and [release policy](https://github.com/keycloak/keycloak/blob/main/RELEASES.md).

## PKI and trust recovery

The existing P2 PKI model is unchanged: separate development issuer keys/trust, server SAN `backend`, client SAN `kong.internal`, distinct serverAuth/clientAuth EKUs, dedicated public edge localhost SAN, explicit enrolled client leaves and issuer trust. Keys remain private owner-only files, RO runtime mounts; offline signing keys are never mounted or committed. Windows ACLs must still restrict the host files.

For leaf renewal, issue into a **new** directory using the retained development CA, preserve owner1000 for Kong and private0600/directory0700, verify SAN/EKU/expiry, install matching cert/key, restart the relevant service and verify the HTTPS/mTLS chain. For CA rotation, add overlapping server/client trust and enrolled new client pins, switch client/server leaves, verify mixed/new generations, then retire old trust/pins and prove old peers are denied. Public edge CA rotation is independent. If verification fails, restore a coherent previously trusted certificate/key/pin/issuer set; do not bypass verification.

The negative tests actually execute missing/untrusted/expired/wrong-EKU clients and expired/wrong-SAN/wrong-chain/wrong-EKU backend servers. Wrong client/server trust fails at TLS; Kong may return upstream502, distinct from app401/403. Original matched certificate/trust rollback recovers200. Production must replace development PKI with owner-managed issuance, renewal, monitored expiry, CA custody and approved recovery; no production CA/key material was created here.

## Operational rollback safety

Before any separately authorized production work, record current digests/config/source, verify encrypted backups and capacity, preserve offline CA/secret recovery through the organization’s process, and quiesce all writers for cold copies. Confirm exact project/volume ownership before every destructive command. A clean Compose project must never be attached to production volumes for testing.

Apply rollback as a new reviewed revert/change commit, with matching source/lock/image/config versions. Do not reset/rebase/amend existing history. Restore old monitoring storage/positions and identity DB as required; preserve failed candidate copies for controlled investigation. An old vulnerable image is a rollback mechanism, not a security-approved release. Re-run negative TLS, real login/RBAC/ownership, network/DB privilege and current ingestion/rule checks before considering recovery successful.

Local original images were retained; no global prune, production-volume mutation, Git push or merge was performed. Actual lab instructions/commands/results are in [the test report](../testing/final-image-remediation-results.md), [inventory](../security/final-image-evidence-20261025/final-inventory.json) and [risk register](../security/final-image-risk-register.md). No further phase or production rollout is authorized by this report.
