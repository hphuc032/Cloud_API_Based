# Kong OSS LTS validation record

2026-10-26; starting HEAD `e7d1c12b04c72c6d21db694a35472dac9d14d953`.
**REL-001 BLOCKED: both inspected OSS artifacts still use OpenSSL 3.2.3.**
No full runtime acceptance is claimed.

## Resource gate and isolation

Windows 11 build 26300, WSL 2.5.9.0 / kernel 6.6.87.2-1, Docker CLI/Engine
29.4.3 and Compose v5.1.3 were checked. Host total visible RAM is about 15.71 GiB;
available samples in this task were about 2.71 and 2.82 GiB (improved from Part A).
Docker reports 20 CPUs and 7.61 GiB RAM ceiling. Initial free disk was about
19.87 GiB on C and 44.07 GiB on D. One pre-existing user PostgreSQL container was
running and was left untouched.

Planned work was sequential binary inspection: 128 MiB container memory/swap cap,
0.5 CPU, 48 PIDs, read-only root, 16 MiB `/tmp` tmpfs, no network, no mounts and
no listeners. A conservative local planning floor of 1 GiB host headroom beyond
the 128 MiB inspection budget was available. This is a safety allowance for these
short commands, not a universal Kong production minimum. All four executions
completed without increasing the cap. Only the official publisher image was newly
downloaded; the library image was reused by immutable digest.

The full multi-service/browser/scanner acceptance needs a separate capacity budget
and measured baseline peak with reserve. This task did not establish that budget
or start heavy work. **The decisive blocker is the absence of a qualifying OSS
LTS artifact**, independently of RAM. Do not represent 2.82 GiB host free RAM as
proven sufficient for the entire suite, or Docker's ceiling as free host memory.

## Executed commands and outcomes

| Check | Actual outcome |
|---|---|
| Git branch, HEAD and approved-baseline ancestry | Expected branch/HEAD; exit 0 |
| Official GitHub release/API and source review | Latest OSS 3.9.4; edition distinction recorded |
| Four live registry lookups: latest + 3.9.4 in both channels | All exit 0; exact platform digests recorded |
| Pull `kong/kong:3.9.4` by pinned digest | Exit 0 |
| Both local image identities | linux/amd64, expected immutable digests; exits 0 |
| Official library nginx/linkage/package/hash command | Exit 0, OpenSSL 3.2.3 |
| Official library direct libcrypto FFI | Exit 0, OpenSSL 3.2.3 / 0x30200030 |
| Kong publisher nginx/linkage/package/hash command | Exit 0, OpenSSL 3.2.3 |
| Kong publisher direct libcrypto FFI | Exit 0, OpenSSL 3.2.3 / 0x30200030 |
| Own labelled inspection containers after execution | None remain; exit 0 |

**Four version/linkage inspection executions succeeded; zero security integration
cases were run.** The lifecycle selection gate failed for both artifacts despite
successful inspection commands. Initial sandbox CIM access was unavailable; the
read-only elevated rerun succeeded. An exploratory Docker version format used
the wrong server field; the corrected command succeeded. Both are documented in
the [preflight receipt](../security/kong-oss-lts-evidence-20261026/preflight-registry.json),
not classified as application failures.

Actual download:

```sh
docker pull --platform linux/amd64 kong/kong:3.9.4@sha256:da2afeecfec0561dd2e06612b09c6283d79245a0387acdc3715271dbf5691a05
```

Exact container argv, stdout/stderr, dates and exits are in
[binary-inspection.json](../security/kong-oss-lts-evidence-20261026/binary-inspection.json).
Commands include `kong version`, `nginx -V`, `ldd`, `openssl version`,
`dpkg-query`, SHA256 of the binary/libraries, and LuaJIT FFI against the linked
library path. For reproduction, use a new unique container name and retain all
isolation/resource flags. ASLR addresses are omitted; vendor build paths are
retained as provenance, not user-local paths. No private keys or tokens were used.

## Mandatory runtime results

| Required group | This task | Historical context only |
|---|---|---|
| Declarative parse, startup/readiness, restart/recreate | NOT EXECUTED | No new compatibility claim |
| Missing/forged/expired JWT, real Keycloak login, issuer/audience | NOT EXECUTED | Existing active OIDC tests preserved |
| RBAC/BOLA, webhook, SSRF, rate limits/recovery | NOT EXECUTED | No assertion/policy changes |
| All 16 TLS/mTLS methods per applicable mode | NOT EXECUTED | Historical 16/16 per mode |
| Certificate and signing-key rotation/outage | NOT EXECUTED | Historical recovery evidence preserved |
| Browser SDK / production SPA | NOT EXECUTED | Historical 9/9 and 8/8 |
| Three real-DNS cases | NOT EXECUTED | Historical 3/3 |
| P5/P6/P7 integration, gateway privacy/correlation | NOT EXECUTED | No monitoring change |
| Full legacy suite | NOT EXECUTED | 213 PASS + 4 historical XFAIL executions |
| Full active suite | NOT EXECUTED | 305 PASS executions / 302 unique cases |
| Fresh exact-image vulnerability scan | NOT EXECUTED | Historical Kong HIGH/CRITICAL 0, not current assurance |
| Rollback drill | NOT EXECUTED | No candidate activated |

No suites were started, so there are no new pytest skip/fail/pass counts. No
expected failures were added, no failures hidden and no DNS/TLS bypass introduced.
All previous results remain historical, not post-upgrade acceptance.

## Continuation only after artifact qualification

From an isolated clean native WSL snapshot, first profile a fresh baseline on
owned Compose projects/volumes and test PKI. Validate the separate candidate
overlay before changing any applicable image pin. Use the existing
`python3 tests/p3/run.py` and `python3 tests/p7/run.py` unfiltered, retaining all
negative tests. Review the [existing Desktop runner precautions](part-a-regression-results.md)
including `P3_RELEASE_BUILD_CACHE=0` / `P4_RELEASE_BUILD_CACHE=0` to prevent global
builder pruning. Focused checks never substitute for full acceptance. If either
resource or security gate fails, stop and keep the approved runtime unchanged.
