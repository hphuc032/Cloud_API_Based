# P4 candidate implementation and validation

Date: 2026-10-09 UTC. Branch: `migration/cloud-api-security`.
Approved base: `e6501b4d64e428e503db5ae2e624e8188ff8bfd7` (P3 DNS evidence);
P3 implementation: `56af7f81b123fcbe649c70dc88ce6421d6636c48`;
P2: `16703e01285938c6b8d002b672f2124e8ab24ac1`.
The exact local P4 commit/bundle digest is in the completion report and transfer
receipt; a commit cannot contain its own final hash. No push, account/credential
change, main merge, production volume/account cutover or P5–P7 work is authorized
or performed here.

## Acceptance gate

**Result: CONDITIONAL.** P4's corrected authentication/browser/gateway/rotation
checks pass; the required public-DNS regression gate remains unresolved.
P3 remains unaccepted because its three real-DNS failures persist. A successful
independent OIDC provider or local commit does not override that gate. No DNS
failure is disabled, skipped, relabelled as xfail or converted into a fake pass.

## Actual completed regression matrix

| Suite / mode | Executed | Passed | Strict expected failure | Failure/error |
|---|---:|---:|---:|---:|
| P0 legacy auth/business/HMAC/SSRF/schema | 89 | 82 | 7 | 0 |
| P1 legacy privileges + populated-DB adoption | 19 | 19 | 0 | 0 |
| P1 legacy host/network/readiness/monitoring/image audit | 16 | 15 | 0 | 1 DNS error |
| P2 legacy TLS sockets/certificates | 22 | 22 | 0 | 0 |
| P2 legacy HTTPS auth/business/HMAC/SSRF | 65 | 57 | 6 | 2 DNS failures |
| P2 legacy host mTLS/rotation/rollback/Vite | 16 | 16 | 0 | 0 |
| P3 legacy provider/mapping | 22 | 22 | 0 | 0 |
| P3 legacy isolation/persistent restart | 3 | 3 | 0 | 0 |
| **Complete legacy P0–P3** | **252** | **236** | **13** | **3 DNS** |
| P4 OIDC/gateway/mapping/business/provider cases | 105 | 99 | 4 | 2 repeated DNS failures |
| P1 privileges in P4 candidate | 18 | 18 | 0 | 0 |
| P2 TLS sockets/certificates in P4 candidate | 22 | 22 | 0 | 0 |
| P4 host isolation/privileges/log ingestion | 5 | 5 | 0 | 0 |
| P3 isolation/persistent restart in P4 candidate | 3 | 3 | 0 | 0 |
| P2 host mTLS/rotation/rollback/Vite in P4 candidate | 16 | 16 | 0 | 0 |
| Real Chromium OAuth lifecycle/state/nonce/outage | 9 | 9 | 0 | 0 |
| Real signing rotation/retirement/JWKS outage/recovery phases | 6 | 6 | 0 | 0 |
| **Corrected P4 outcome across full + browser recovery** | **184** | **178** | **4** | **2 DNS** |
| **Combined recorded executions** | **436** | **414** | **17** | **5 DNS executions / 3 unique cases** |

Separate checks: three focused non-DNS recovery cases **3 passed** before the
full candidate; P3 inactive-client contract **19 assertions passed**; P4 session
contract **passed** (script assertions, not an invented pytest case count);
frontend production build **passed**, Vite 6.4.3, 1649 modules, **3.18 seconds**.
Python compilation, browser JS syntax and staged Git whitespace checks passed.
There are **0 skipped/disabled cases, 0 XPASS, 0 unresolved non-DNS test failures**.
All requested test groups executed; the post-DNS-repair focused/full rerun remains
unexecuted because no working resolver was restored. Production cutover and real
account/client changes were deliberately not executed; they are outside approval.

These totals explicitly combine projects; they are not one all-green full run:

- Full P4 `cloud-api-p4-34bab8e8c62e`,
  **05:50:25–06:07:16 UTC**, exit 1: 139 passed / 4 xfail / 2 DNS in the 145-case
  pytest run (229.44 seconds), host 5+3+16 passed, rotation six phases passed.
  Browser launch stopped before cases on occupied port 5174.
- Corrected browser `cloud-api-p4-407858bc1ce0`: fresh project, final frontend,
  **9/9 passed**, wrapper exit 0. Exact timestamps are in the linked evidence.
  Intervening browser attempts and corrections are disclosed below.
- Full legacy `cloud-api-p3-b69c8dae86ca`,
  **06:44:38–06:56:56 UTC**, wrapper exit 1: **236 passed / 13 xfail / 3 DNS**.
  The 108-case P0/P1 pytest stage passed 101 + 7 xfail in 20.88 seconds; the
  87-case P2 stage passed 79 + 6 xfail with two DNS failures in 215.52 seconds.
  All project containers, networks, volumes and private temp data were cleaned up.

Approved P2 was **214 passed / 13 xfail / 0 failures (227)**. The same historical
portion here is **211 passed / 13 xfail / 3 DNS (227)**; P3 adds 25 passing checks.
This exactly matches P3's previous acceptance-recovery outcomes. P4 adds the
explicit OIDC release outcome above. P1 least privilege/isolation, P2 verified
HTTPS/mTLS, existing legacy login/JWT/refresh/logout and all DB RBAC/ownership
tests remain successful. The original seven defects remain in the legacy release.

### Exact remaining failures and DNS evidence

| Unique test | Required assertion/query | Actual error and classification |
|---|---|---|
| `host_checks.execute.<locals>.DeploymentChecks.test_public_dns_for_current_ssrf_validation` (`tests/p1/host_checks.py:152`) | Backend namespace `bool(socket.getaddrinfo('example.com',443))` is True | `socket.gaierror: [Errno -3] Temporary failure in name resolution`; subprocess exit 1 / `CalledProcessError`, unittest ERROR. Runtime resolver infrastructure. |
| `tests/p2/test_https_business.py::test_https_ssrf_uses_real_dns_and_preserves_roles[staff-200]` (`:72`) | Verified HTTPS POST `/api/v1/security/fetch-url`, `https://example.com/test`, status 200; validator `getaddrinfo('example.com',None)` | AssertionError; unchanged DNS-error path returns 400 `Unable to resolve hostname`. Same resolver infrastructure, repeated in the P4 OIDC suite. |
| Same function `[admin-200]` | Same query/request with current DB admin authority | Same result/root cause; repeated in P4. |

Fresh diagnostics **06:47:31/06:47:36 UTC** show Agent `/etc/resolv.conf`
`172.31.0.93`; example.com and allowed control pypi.org fail both A/AAAA via
getaddrinfo. Connected UDP and TCP to that supplied resolver port 53 return
`[Errno 111] Connection refused`. Actual legacy backend uses Docker `127.0.0.11`,
upstream `host(172.31.0.93)`, no overrides; both external names fail errno -3,
while `postgres` and `kong` resolve their actual private project IPs. Earlier P4
backend diagnostics also resolve the required `identity-edge` alias. A separate
late diagnostic was terminated by the candidate's normal cleanup (exit 137); it
is not a failed application test or a substitute for the completed fresh probes.

The unchanged SSRF source SHA-256 in approved P1/P2/P3/P3 evidence and P4 is
`b84670ffa50dca7510bbea1f33dc58a323fc00445e041053e7c5765429495ad3`.
Network tests verify the application transport is not an all-internal egress
trap. No application regression or policy relaxation was detected. The supplied
resolver path is unavailable; platform listener/firewall/sidecar internals are
not accessible, so no unsupported claim about an authoritative Internet outage
or the exact platform-side component is made.

### Historical defects and replacement tests

| Defect | Legacy regression | P4 release |
|---|---|---|
| D01 signed local access JWT missing exp | Strict xfail remains | Replaced by mandatory expiry negatives at gateway and backend; legacy tokens rejected |
| D02 signed local non-UUID subject produces 500 | Strict xfail remains | External opaque subject mapping/validation replaces UUID casting; malformed/unmapped identities receive controlled 401 |
| D03 signed non-object webhook JSON | Strict xfail remains | Same strict xfail, unchanged HMAC business behavior |
| D04 webhook replay accepted twice | Strict xfail remains | Same strict xfail |
| D05 IPv4-mapped IPv6 loopback validation | Strict xfail remains | Validator unchanged; historical characterization remains, not claimed fixed |
| D06 null product price; D07 null user role | Strict xfails remain | Same two strict xfails |

Local login/register/refresh/logout tests run in legacy; P4 replaces their browser
use with real code/PKCE/session tests and independently verifies retired local
issuance returns 410. P3's intentionally-local-auth assertion runs unchanged in
legacy and is replaced by `test_real_access_and_legacy_rejection` for P4. Its
fixture-specific binding preservation check is replaced by existing-ID/order/role
checks with genuine mapped identities. P3 client policy gets a P4-specific exact
URI/origin comparison for the additional approved test callback/logout values.
Nothing was silently removed from the full historical regression.

Public sanitized evidence: [all individual outcomes](p4-case-results.json),
[discovery/JWKS, source hashes, browser/rotation and DNS](p4-evidence.json),
[executed command arrays](p4-commands.json), [exact changed files](p4-files.txt),
and [P2 TLS evidence](p4-tls-evidence.txt). Raw stdout/JUnit/inspection files and
intermediate diagnostics are ignored local artifacts. No tokens, password values,
private keys or production user exports are included in these public records.

## Implementation and review decisions

- [Architecture, actual OAuth flow, validation flow and route matrix](../authentication/p4-architecture.md).
- [Realm, explicit account migration/provisioning and release rollback](../deployment/p4-cutover.md).
- [Verified signing-key synchronization, overlap, retirement and rollback](../deployment/p4-key-rotation.md).
- [Workspace B bundle import and authorized normal push procedure](../deployment/p4-workspace-transfer.md).

The P4 overlay selects one exact HTTPS issuer, `florasecure` realm and public
`florasecure-spa` client, API audience `florasecure-api`, RS256, code/PKCE S256,
300-second access lifetime, rotating refresh (zero reuse), 30-minute idle and
eight-hour maximum sessions. Registration/password/implicit/service-account SPA
flows remain disabled. Development callback/origin/logout lists are exact HTTPS
localhost entries, never wildcard production placeholders. Realm discovery's
global advertised grant list is not the SPA's enabled-flow policy; real negative
grant/redirect/PKCE tests exercise the client policy.

React uses `keycloak-js` **26.2.4**, pinned in the lockfile; Playwright is **1.58.2**.
The adapter owns one-time state, nonce, code/verifier and session lifecycle. Tokens
stay in memory; obsolete `fs_*` keys are removed. Reload uses Keycloak SSO and a
new code exchange. Refresh is single-flight; failure clears authentication. Logout
uses POST and exact redirection. `/auth/me` supplies the PostgreSQL user/role.
There is no BFF, HttpOnly application session or legacy-login fallback.

Actual gateway image: Kong OSS **3.8.0**, `kong:3.8`, image
`sha256:bfb293c155dd5d4aea6aaaaa220b998d8a1c4f3faa2ee6e0ea43bf59f1dae46c`.
Native JWT credentials use verified public JWKS, header `kid` and RS256. Kong
rejects missing/bad signatures, expiry and excessive remaining lifetime before
business logic. Keycloak omits optional `nbf`; Kong requires every configured
time claim, so gateway `claims_to_verify` is `exp`. FastAPI independently checks
applicable `nbf`, exact issuer/audience, required exp/iat/sub/aud/iss, Bearer/azp,
bounded lifetime/subject and its own signature through HTTPS JWKS. Wrong-issuer,
audience/type tokens can pass the limited OSS layer but receive backend 401.
Native Kong schema parsing and actual requests establish compatibility; no
Enterprise OIDC plugin, symmetric-secret workaround or copied private signer is
used. Keycloak remains the digest-pinned P3 **26.2.5** provider.

The signing-key consumer is not an application identity. The limiter explicitly
retains **60/minute per IP** for public and valid authenticated traffic. Native
JWT executes before the limiter: invalid JWTs are rejected before its counters,
which is an operational limitation, not a claim of pre-authentication throttling.
Exact CORS, public product GET/HEAD, health, HMAC webhook and protected business
routes are separated; local token routes are 410 only in OIDC mode and debug
signature/admin/unmatched endpoints are not exposed.

Application IDs/relationships and P3's composite-PK external identity schema are
retained; no Alembic revision or destructive schema change is needed. The only
new runtime DB privilege is mapping SELECT in OIDC mode. Unknown external
identities are denied. The operator tool defaults to dry-run, requires exact
review SHA for apply, locks/rechecks inspected state, rejects duplicate/colliding
bindings and never links by email. Existing UUIDs, historical orders, roles and
active flags survive. Explicit new provisioning creates only customer accounts
with unknown random local passwords; existing-password rollback requires review.

Main Compose, P3 realm, P2 PKI/upstream mTLS, business routers/services/models,
SSRF validator and historical defect tests remain unchanged. Explicit legacy
release regression is separate from OIDC; there is no runtime fallback. P4
authentication is not enabled against existing production data.

## Test method, evidence and corrections

Tests use disposable UUID Compose projects and volumes, runtime CSPRNG secrets,
generated P2/identity PKI and actual persistent PostgreSQL-backed Keycloak.
Four disposable identities and an ephemeral RSA signing provider support real
code/PKCE tokens and trusted-signature negative claim tests. Backend bypass
tests still use a properly enrolled mTLS client; no API authentication/JWKS is
mocked. Browser trust verifies CA and SAN, never `ignoreHTTPSErrors` or certificate
flags. Its private Compose alias maps only the inspected service IP, not public
DNS. The test-only container runs Chromium without its process sandbox to support
this isolated host; it receives no DB secrets, application private keys or Docker
socket. This is not a production browser security setting.

This 32-GB host uses Docker `vfs`. Verified flattened dependency bases and a
sanitized local build context were used; current application/test sources are
copied afresh and P4 checks Python/realm SHA-256 before testing. Normal repository
Dockerfiles remain the reproducible build path on a suitably provisioned host.
Optional staged startup audits/removes completed own bootstrap jobs, and the
probe worker executes fresh Python probes with unchanged networks/fixtures/TLS.
Legacy migration containers remain for the original restart/no-rerun assertion.
No unrelated service/data/image was removed.

Earlier development failures were diagnosed and are not counted as passes:

- Kong requires `~/...$` rather than unsupported `~^/...` routes. Native parser
  rejected the initial configuration; corrected regexes were parsed and exercised.
- Requiring optional `nbf` in Kong rejected genuine Keycloak tokens. Gateway
  checks now reflect supported mandatory `exp`, with independent backend nbf
  negatives retained; token contents and certificate checks were not altered.
- Stale short-lived private admin fixture tokens, missing launch PYTHONPATH,
  job import/config coupling and subprocess duplicate environment arguments were
  corrected and rerun.
- Three non-DNS failures in the preceding 145-case candidate were fixed: unordered
  Keycloak URI/origin lists now compare exact sets plus cardinality; rate limiting
  explicitly preserves IP quotas; P2's HTTP-401 metadata assertion distinguishes
  native gateway rejection from an upstream legacy response. All three focused
  cases passed before the latest full 145-case run. The original legacy Via
  assertion and every socket/certificate negative remain.
- A removed completed dependency made `compose start identity-edge` unsuitable
  for outage recovery. `up --no-deps --wait` and the documented refresh backoff
  restored verified readiness; complete rotation/outage checks were rerun.
- Browser wrapper launch, orphan npm/Vite on exact port 5174 and unrelated external
  font/full-page-load waits were diagnosed. The runner uses Chromium's ELF binary,
  private NSS trust, direct Vite lifecycle cleanup, DOM plus application assertions
  and test-only blocked optional Google Fonts. IdP/API/SSRF tests remain real.
- A premature callback interception assertion did not actually alter state.
  The corrected test changes only state in the genuine callback URL at document
  initialization, before SPA execution, then requires a controlled rejection and zero code exchanges.
- An intermediate focused project could not start Grafana: `mkdir /var/lib/grafana/png:
  no space left on device`. Only 30 completed own P4 image tags were removed,
  reclaiming roughly 4 GB before a fresh retry. No application/TLS expectation
  was changed to handle capacity.
- Eight real browser cases then passed; the outage case exposed the adapter's
  top-level navigation to a connection-error page. A bounded verified discovery
  preflight now checks exact endpoints before init/manual login and keeps failures
  in the SPA. It does not replace OAuth exchanges or weaken TLS/claim checks.

## Limits and required follow-up

Restore the supported runtime resolver, verify actual Agent/backend getaddrinfo,
then rerun the three affected cases first and the complete legacy/P4 suites.
The saved environment `start_skill` draft describes this workflow and requires
user review/save/publication; saving it does not repair runtime DNS. No remote
credentials were changed or new secret values placed in the draft.

Production cutover/client update/account manifests/certificates were not applied
to existing data. Persistent realms skip import and require the reviewed update
procedure. JWT logout/session revocation does not instantly revoke previously
issued access tokens (up to 300 seconds); signing-key retirement can also take the
60-second backend cache TTL unless emergency restart is used. DB role/is_active
changes are enforced per request. Warm known keys survive an outage only within
TTL; expired-cache refresh failure denies. Rotation requires serialized operator
parse/digest promotion/reload, not an automatic scheduler or public admin API.

Browser XSS can access memory tokens; BFF, broader CSP/XSS hardening, MFA,
pre-authentication abuse controls, HA, SQL TLS/at-rest encryption, backup/DR
certification and current CVE auditing were not implemented or certified. Some
existing image references use version tags rather than immutable digests; no
current CVE-free claim is made. P5–P7 remain outside scope.

Git diff summary: **59 files changed, 19002 insertions(+), 677 deletions(-)**. Most additions are explicit command and individual-case evidence.
