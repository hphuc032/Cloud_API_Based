# P7 final validation candidate

Run only against generated disposable services:

```sh
python3 tests/p7/run.py --defer-public-dns
python3 tests/p7/run.py --focus recovery --defer-public-dns
python3 tests/p7/legacy.py --defer-public-dns
```

The user's explicit deferral schedules the three inherited real-DNS IDs for later.
`-k` selects all other pytest cases; unittest selection omits only the named public
DNS host check. The tests/assertions are unchanged, never skipped/xfail-converted.
The candidate records the two exact deselected names and scheduling-driver hash;
legacy records its selected expression and the exact unexecuted host ID. Strict
acceptance remains BLOCKED even when all executed cases pass. Without the flag,
all original cases run and failures remain failures.

`run.py` adapts the established P6 driver, adds current-source verification,
request/SQL/Loki attack records and paired recovery. `recovery.py` streams private
role/verifier/DB archives only in memory into two fresh instances, compares rows,
constraints/owners and privileges, runs actual recovered PKCE authentication and
API authorization, recreates backend and returns to untouched original DB volumes.
It only accepts generated P7 project names. Private DB aliases are changed only
inside that disposable lab. Collector mounts and metadata are renewed after
container recreation; Grafana recreation/dashboard/rule queries and new correlation are
checked after restart. No application security behavior changes.

`launch.py` uses the existing destructive-fixture guard (APP_ENV=test,
P0_ISOLATED=1, exact postgres/p0_baseline) and original P4 reviewed identities.
`verify_recovered.py` is read-only and avoids destructive autouse fixtures.
`legacy.py` wraps the unchanged P3 driver; PyYAML preserves Compose !reset tags.
`evidence.py` extracts per-case results and explicitly allowed public JSON only,
filters stale artifacts by run start, and compares all security/runtime and P0–P6
test files with approved P6. Raw container inspection, logs, fixture credentials,
private certificates and dumps must stay ignored. Curated evidence still requires
secret review before commit.

Full candidate, focused recovery and historical results are separate observations,
not additive unique security-case counts. Optional performance figures and current
advisory scans must never be inferred from test elapsed time/offline npm audit0.
See [P7 report](../../docs/testing/p7-results.md), [reproducibility](../../docs/deployment/p7-reproducibility.md)
and [recovery/rollback scope](../../docs/deployment/p7-backup-recovery.md).
