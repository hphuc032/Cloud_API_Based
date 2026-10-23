# P6 retention recovery: diagnosis and proof

The original 480-second failure was a test lifecycle error, not proof that Loki
2.9.8 cannot delete expired filesystem chunks. The final probe passes repeatedly
without reducing the 168-hour retention policy. Overall P6 acceptance remains
subject to the DNS gate and the final regression report.

## Version-compatible root cause

The actual binary is Loki **2.9.8**, revision **94e00299ec**, Go1.21.9. This version
supports the configured filesystem object store, v11 boltdb-shipper schema and
24-hour index period with compactor retention. An upgrade/storage migration was
not needed to demonstrate deletion. Its age/support status remains a production
risk; passing this experiment does not certify vulnerability support.

Official v2.9.8 source URLs and SHA256 are in
[p6-recovery-retention-sources.json](p6-recovery-retention-sources.json).
`pkg/storage/stores/shipper/index/table.go` defines
`ShardDBsByDuration = 15 * time.Minute`. A write shards the local BoltDB by **write
wall time**, not the log's old event timestamp. `getOldestActiveShardTime()` adds
a one-minute safety buffer. Ordinary handover excludes the still-active shard.
`/flush` persists chunks/local indexes; it does not force that handover.

The original clean run flushed at approximately 2026-10-21T16:51:26Z and ended
about 16:59:26Z. Its 16:45 write shard could not become eligible before 17:01.
Accelerating compaction to five seconds could not make an unshipped index visible
to the compactor. Logs showed compactor cycles but no uploaded probe table or
retention markers. Explicit `shared_store: filesystem` alignment was appropriate,
but could not fix this lifecycle timing by itself.

`TableManager.Stop()` calls `handoverIndexesToShipper(true)`. The corrected probe
uses a supported graceful stop/restart: both index tables upload, the compactor
finds the expired entry, creates a marker and the sweeper deletes its chunk. No
file timestamp, shard name, system clock, retention period or delete API is used
to manufacture eligibility.

## Cache visibility and logical expiry

A newly written eight-day-old chunk has a recent filesystem mtime, but its
encoded event time makes it retention-eligible once its index is shipped. The
probe decodes each chunk object key and matches its millisecond event time to the
accepted old/current samples. It records size and SHA256 before/after deletion.

Physical deletion and query-cache convergence are separate. In a diagnostic run,
shared old index/chunk files disappeared and the success metric incremented while
the single-binary process still returned the cached historical record. A later
accelerated single-binary run converged and passed after about 462 seconds.
Local writer index snapshots and chunk caches must not be mistaken for proof
that the physical object still exists.

Production now explicitly sets `limits_config.max_query_lookback: 168h`, matching
the unchanged physical policy. This makes the public Loki read contract exclude
expired logs while caches converge. Writer old/current queries are asserted
before and after deletion. This is a logical read limit, not physical-deletion
proof.

The independent verification querier mounts only the probe's object storage
read-only, has its own temporary cache, runs `-target=querier`, uses the real
compactor endpoint, and explicitly sets **max_query_lookback: 0s**. Therefore its
old query becoming empty cannot be explained by the new lookback filter. It does
not query the writer/ingester. `query_store_only` on the single-binary target was
an unsuccessful intermediate experiment: that target delegates recent storage
queries to ingester lookback, causing a missing current control. That failure is
retained and is not counted as a pass.

## Exact acceptance conditions

Each fresh random Compose project must prove all of the following:

1. A real push accepts both samples, and two distinct physical chunk objects exist.
2. The independent reader initially returns old=1/current=1.
3. Its unbounded supported query later returns old=0/current=1.
4. The exact old chunk object no longer exists, while the current object's size
   and SHA256 remain identical.
5. `loki_boltdb_shipper_retention_sweeper_chunk_deleted_duration_seconds_count`
   with `status="success"` is positive.
6. The writer returns old=0/current=1 after deletion.
7. The project's own containers, network and volumes clean up successfully.

The metric is a histogram **observation count** for successful chunk deletions.
Its `_sum` is elapsed time; bucket counts are cumulative, not extra deletions.
`status="notfound"` can arise from duplicate markers and is not accepted as a
successful deletion. `retention_sweeper_marker_files_deleted_total` counts marker
files processed, not physical chunks, and cannot satisfy condition 5 alone.

Authoritative repeats using the portable Python stdlib probe image:

| Disposable project suffix | Unbounded old/current before | After | Writer after | Success deletion count | Query/deletion observation loop |
| --- | --- | --- | --- | ---: | ---: |
| `8fd1584c3c` | 1 / 1 | 0 / 1 | 0 / 1 | 1 | 65.27s |
| `7c3b4bd0c3` | 1 / 1 | 0 / 1 | 0 / 1 | 1 | 70.39s |

Both preserved the current object's SHA256 and exited/cleaned up with code 0.
These durations exclude startup/seed/graceful shutdown. Full UTC timings, exact
argv, object keys/hashes, configurations, metric samples and selected exact log
lines are in [p6-recovery-retention.json](p6-recovery-retention.json). Raw synthetic
storage logs remain in the project-specific ignored artifact directories; their
SHA256 is recorded. Original failure evidence remains in
[p6-retention-clean-evidence.json](p6-retention-clean-evidence.json).

## Acceleration, environment and limits

The test alone admits old samples and accelerates flush, compaction, index cache
validity, shipper resync and delete delay. The 168h policy remains unchanged. The
sweeper's own one-minute marker-list cycle is not patched. Production remains
one-minute compaction and **two-hour** physical deletion delay. The full two-hour
wall-clock delay, natural shard rollover, production-volume migration,
marker-recovery across a compactor restart and backup/restore are not validated
by these accelerated experiments. No production volume was opened or deleted.

The default Docker client configuration `/home/agent/.docker/config.json`
injected HTTP/HTTPS proxy172.31.2.109:8080 with NO_PROXY limited to loopback.
Consequently private Go gRPC/Python HTTP attempted an unreachable external proxy
from the isolated storage network. The sanitized configuration evidence is in
[p6-recovery-proxy-diagnostics.json](p6-recovery-proxy-diagnostics.json). The Loki service explicitly clears proxy
variables and sets NO_PROXY for its private filesystem/RPC deployment; the probe
uses `ProxyHandler({})`. The independent reader initially needed an explicit
compactor address and a writable temporary cache. These intermediate failures
are preserved. None is a DNS repair or a certificate-verification bypass.

Run twice, serially:

```sh
python3 tests/p6/retention.py
python3 tests/p6/retention.py
```

The default probe is `python:3.11-slim`; `P6_RETENTION_PROBE_IMAGE` can select its
recorded immutable digest. Actual image IDs/digests are recorded in
[p6-recovery-image-provenance.json](p6-recovery-image-provenance.json). The reader
has a read-only root/object mount, dropped capabilities, no-new-privileges and a
temporary writable cache. Neither service publishes host ports.
