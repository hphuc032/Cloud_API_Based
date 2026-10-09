# Disposable P4 validation

From the repository root, install the existing backend requirements, frontend
locked dependencies and a Chromium binary plus NSS `certutil` on the test host.
The browser driver currently requires Linux's Chromium ELF binary at
`/usr/lib/chromium/chromium` and NSS `certutil`; a wrapper script alone is insufficient.

```sh
python -m pip install -r backend/requirements.txt
npm ci --prefix frontend
node tests/p4/test_session.mjs
npm run build --prefix frontend
python tests/p4/run.py
# Optional fresh focused recovery; not a complete acceptance run:
python tests/p4/run.py --focus browser
python tests/p4/run.py --focus rotation
# Full historical release regression uses its original auth mode:
python tests/p3/run.py
```

`run.py` generates a random `cloud-api-p4-*` project, new secrets, three P2 trust
authorities and separate identity PKI. It imports an ephemeral RSA provider and
creates random-password Keycloak accounts only in the disposable DB. Test signing
material/credentials remain under a private temporary parent and are deleted in
`finally`; no production data is used. Privileged fixtures explicitly map trusted
subjects to existing generated application user IDs. Business API assertions use
actual Kong HTTPS, backend mTLS, current DB RBAC and genuine Keycloak access tokens.
Negative claim tests use the same disposable trusted signing provider, so they
exercise claim policy after successful signature validation.

The real browser runs as the host numeric UID in a disposable read-only container,
using the installed system Chromium and libraries through read-only mounts. It
trusts generated public test CAs in an isolated NSS database via `XDG_DATA_HOME`,
with a private profile; HOME and the host trust store are never modified. It dynamically resolves the
private Compose alias `identity-edge` to its inspected actual container address.
This is test service routing, not a public DNS substitute. No public hosts are
mapped, DNS tests retain libc `getaddrinfo`, and HTTPS CA/SAN checks remain enabled.
The separate container avoids Chromium preferentially using an existing legacy
host NSS store. CDP binds a random loopback port and is removed after testing. The frontend runs on verified
HTTPS localhost:5174 and proxies to the random loopback Kong HTTPS port with a
trusted Node extra CA. Only the private browser runtime directory is mounted writable; database secrets
and application private keys are absent. Traces/screenshots/tokens are not committed.
Navigation waits for DOM readiness followed by actual authentication/UI/API
assertions. Optional Google Fonts requests are blocked in this test browser to
avoid unrelated external typography loading; Keycloak/API requests remain real,
verified HTTPS. The mandatory public-DNS/SSRF tests are unaffected and still fail
when the supplied runtime resolver is unavailable.

The rotation probe stages a genuine passive Keycloak key, synchronizes parsed
public credentials, activates it, proves old/new overlap, removes the old provider
and restarts the backend for emergency trust retirement. A real identity-edge
outage tests known-key warm cache, expired-cache denial, unknown-key refresh
throttling and failed-render preservation of active Kong config. Actual backend
default cache expiration is tested; it is not mocked.

Only supported cloud build overlays may be passed using `P4_BUILD_OVERLAY`;
production Compose settings remain unmodified by local build optimizations.
`P4_RELEASE_BUILD_CACHE=1` releases unused builder cache. Optional
`P4_RELEASE_EXITED_JOBS=1` stages the same readiness/job ordering and audits/removes
only completed disposable job containers to bound Docker vfs disk consumption.
Application/identity volumes and live services remain until final cleanup. P3 has
the analogous `P3_RELEASE_EXITED_JOBS=1` option, retaining the migration container
for the existing no-rerun assertion. Tracked tests and security expectations are
unchanged by these orchestration options. All container-executed source files and
realm JSON are SHA-256 checked against the P4 checkout before tests.

Raw evidence is ignored under `tests/p4/artifacts`. Preserve sanitized outcome,
public discovery/JWKS and command records under `docs/testing`. Test suite failures
produce exit 1; DNS failures are not converted into skips or xfails. No production
acceptance is claimed by successful build or isolated subsets alone.
