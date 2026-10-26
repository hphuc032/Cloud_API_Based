# Kong OSS / OpenSSL LTS remediation assessment

2026-10-26. Branch `migration/cloud-api-security`.
Approved baseline: `d79cb6060e95ba58cd797b6ef24b3b938ae80b8a`.
Starting HEAD: `e7d1c12b04c72c6d21db694a35472dac9d14d953`; that documentation
commit and all previous evidence are preserved.

**REL-001: BLOCKED. No official OSS candidate qualified or selected. Overall
production release: BLOCKED.** This follow-up expands the previous
[Part A assessment](part-a-kong-openssl-assessment.md) to the Kong publisher's
separate image channel and checks live official release/registry information.

## Official release and edition findings

The [official latest release](https://github.com/Kong/kong/releases/latest)
resolved to 3.9.4, published 2026-10-12. The first 30 release records returned by
the GitHub API contain no newer stable OSS release. The current
[Docker Official Images definition](https://github.com/docker-library/official-images/blob/master/library/kong)
also points `latest` / `3` to 3.9.4. Live registry checks confirmed:

- `kong:latest` and `kong:3.9.4` resolve to the same official image index.
- `kong/kong:latest` and `kong/kong:3.9.4` resolve to another index; this is Kong's
  [verified publisher OSS channel](https://hub.docker.com/r/kong/kong/tags), not
  the Enterprise image. The actual package and binary both report 3.9.4.
- The [3.9.4 repository license](https://github.com/Kong/kong/blob/3.9.4/LICENSE)
  is Apache-2.0. This is not a grant of Enterprise support or maintenance.

The [Kong Gateway changelog](https://developer.konghq.com/gateway/changelog/)
explicitly covers **Enterprise**: entries such as 3.10.0.12 / OpenSSL 3.5.6 and
3.16.0.0 / OpenSSL 3.5.8 do not establish an equivalent OSS Docker release. No
Enterprise image was downloaded, selected or silently substituted. Search results
with older cached release lists were not used instead of the live API/registry.

No official OSS release newer than 3.9.4 was identified in these checked sources.
This is a dated finding, not a promise about future vendor releases or a claim
that all possible third-party registries were exhaustively searched.

## Immutable artifacts and actual crypto

| Artifact | Index / recorded descriptor | linux/amd64 child manifest |
|---|---|---|
| Baseline `kong:3.9.3` | `sha256:92035d16d7ff86b7bc12fb1d0090d29357d924238b1880f78735f3f2fea6b631` | `sha256:6328373b745d9228d42d5cfe8338ab39370a13aef8fcb0d0d72c0caa6eb3b1d7` |
| Official library `kong:3.9.4` | `sha256:aa4a4687b1330e427ad0d3b27a0606b833894297c78abf1a212edc9ba73c8620` | `sha256:45993f7e2c77036e52e553419553f58eb06b7dd87513e3350e230dc04b5ebe6c` |
| Kong publisher `kong/kong:3.9.4` | `sha256:da2afeecfec0561dd2e06612b09c6283d79245a0387acdc3715271dbf5691a05` | `sha256:64194b84dce63b3f00b1a5b40a8147f928b30749b5f621d73d74fdd54877a9db` |

Both 3.9.4 images were executed on linux/amd64 in this follow-up:

| Measurement | Result in both 3.9.4 artifacts |
|---|---|
| Kong binary / installed package | 3.9.4 / 3.9.4 |
| nginx build | OpenResty 1.25.3.2, built with OpenSSL 3.2.3 |
| `ldd` | Dynamic `libssl.so.3` and `libcrypto.so.3` under `/usr/local/kong/lib` |
| Runtime FFI of that `libcrypto.so.3` | OpenSSL 3.2.3 (3 Sep 2024), `0x30200030` |
| OS CLI | OpenSSL 3.0.13; package `3.0.13-0ubuntu3.16` |
| nginx binary SHA256 | `9ed0770ad5e2be1cebd2127f01e3b1741ddc4a89a56ca9a80e1d19f981c0bbed` |
| linked libssl SHA256 | `fd7421f3b08315ee1fad668f95a51317acdb984f9c8ef966ae14aac14c166107` |
| linked libcrypto SHA256 | `f7b9d933c3a00086355d63a7810bd117de26139987d0c051af2bea1778c80a21` |

The matching three hashes establish identical inspected crypto/nginx files across
these two images, not identical entire images. The old 3.9.3 linkage result is
referenced from the immutable [Part A receipt](part-a-evidence-20261026/kong-crypto-inspection.json);
it was not rerun in this follow-up. Fresh
[binary receipts](kong-oss-lts-evidence-20261026/binary-inspection.json) distinguish
package/CLI, build flags, dynamic linkage and runtime library calls. No TLS listener
was started, so these are not fresh handshake results.

## Lifecycle and security provenance

[OpenSSL's roadmap](https://openssl-library.org/roadmap/) gives 3.2 public EOL as
2025-11-23 and 3.5 LTS support through 2030-04-08. The
[download page](https://openssl-library.org/source/) listed 3.5.9, a 2026-09-29
security patch release, when reviewed. A future 3.5 build must still be assessed
for current patches, providers, advisories and actual linked bytes.

The [official image Dockerfile at its pinned revision](https://github.com/Kong/docker-kong/blob/8b2c2238ca0607e210cada8223407c13fedec943/ubuntu/Dockerfile)
uses the community package (`ASSET=ce`), Ubuntu Noble and a SHA256-checked Kong
3.9.4 package. Registry annotations identify this source revision. No image
signature verification is claimed. The
[OSS changelog](https://github.com/Kong/kong/blob/3.9.4/CHANGELOG.md) records the
3.9.4 clustering SQL injection fix (CVE-2026-1907) and the prior 3.9.3 nginx
CVE-2026-49975 patch. Neither establishes extended support or an LTS crypto
upgrade; the actual runtime remains 3.2.3. Clustering SQLi reachability was not
proven in this DB-less deployment and is not relabelled as a crypto fix.

No authoritative ongoing backport/support coverage for the exact 3.2.3 artifact
was demonstrated. Its version string alone would not disprove a vendor backport,
but absent such evidence the lifecycle gate remains unresolved. Historical Kong
HIGH/CRITICAL scan count was 0 on October 25. **No fresh vulnerability scan ran;
current candidate HIGH/CRITICAL count is unknown**, not zero. Unrelated release
risks remain as documented in [Part A](part-a-controlled-remediation.md).

## Configuration compatibility and preserved controls

| Existing contract | Reviewed implementation | Candidate validation |
|---|---|---|
| DB-less routing | Base `gateway/kong.yml`; active OIDC config generated by `backend/deployment/kong_jwks.py` and P4 key job | NOT EXECUTED; no qualified LTS target |
| RS256 / kid / exp | Built-in JWT plugin, header token, exp/max lifetime; independent backend issuer/audience/type and DB RBAC/BOLA | Not replaced with Enterprise OIDC plugin |
| HTTPS / upstream mTLS | TLS 1.2/1.3, dedicated client key, CA trust, server verification/depth, `https://backend:8443` | All original negative CA/SAN/EKU cases remain mandatory |
| Rate/forwarding boundary | P5 preauth limiter, shared dictionary, local limit policy, untrusted client forwarding | No relaxation |
| P6 Lua/telemetry | Custom plugin and error-ring processing, bounded reasons, correlation and redaction | OpenSSL error-message differences require testing on any future LTS candidate |
| Runtime privilege | UID 1000, protected key modes, read-only mounts, `/run/kong` writable prefix | No change |
| Networks / data | Kong only edge/API transport, no application DB membership | No change; membership is not encryption or a directional firewall |

The actual Compose overlays and Lua/JWT generator were read. Configuration
compatibility is **not demonstrated merely by sharing a major version or ABI**.
No candidate overlay or active image-reference change was made because neither
artifact passes the crypto selection gate. Windows OpenSSL 4.0 in the user's
Labs directory was not accessed or copied; no custom runtime or library swap
was built. Source, tests, historical evidence and user services remain intact.

## Outcome and next decision

See [validation/resource report](../testing/kong-oss-lts-validation.md) and
[rollback gates](../deployment/kong-oss-lts-rollback.md). Research and small binary
checks are complete; implementation acceptance is BLOCKED. A future official OSS
artifact with supported, patched crypto can reopen validation. A custom
Kong/OpenResty build or edition/gateway change is a separate proposal requiring
maintainership and scope decisions, not an automatically approved workaround.

Machine-readable provenance: [official sources](kong-oss-lts-evidence-20261026/official-sources.json),
[preflight/live registry](kong-oss-lts-evidence-20261026/preflight-registry.json),
[actual binary commands](kong-oss-lts-evidence-20261026/binary-inspection.json).
No Loki remediation, Part B, push, merge or production deployment was performed.
