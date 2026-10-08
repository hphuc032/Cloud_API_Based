# P3 OIDC preparation tests

From repository root:

```sh
node tests/p3/test_client.mjs
python tests/p3/run.py
```

Install frontend dependencies with `(cd frontend && npm ci)` before the full runner,
which includes the existing live Vite proxy test.

Requires Docker Compose with `!reset`/`!override` support and host Python with the
repository's pinned cryptography package. Use backend/.venv/bin/python after
installing backend/requirements.txt. Production secrets/data/PKI are not used.

The runner creates a random project, temporary secrets and separate identity/API
certificate authorities. Both databases use fresh project-scoped volumes. It runs
22 P3 integration cases, three provider infrastructure checks, full P0/P1/P2 pytest
and both historical host suites. It always removes its own containers, networks and
volumes. It never removes or mounts unrelated deployments.

New Keycloak users have random runtime passwords and are deleted after testing.
No seeded passwords or private keys are in the source realm. Test-only secret mounts
are world-readable inside the assigned containers because Compose preserves source
permissions; their temporary host parents remain mode 0700. Deployment secrets must
use equivalent host ACL protection and per-service reader permissions.

The Node command checks 19 assertions in the inactive client preparation module,
including exact callback, state, nonce, issuer, audience and expiry rejection. No
frontend authentication cutover or unverified token parsing is implemented.

OIDC/JWKS requests and real authorization-code/token exchanges verify certificates
and hostnames. RS256 access/ID tokens are signature-verified against fetched public
JWKS, with issuer, audience, expiration, ID nonce and at_hash checked. Negative tests
include missing/plain PKCE, wrong verifier, code reuse, incorrect redirects, implicit/
hybrid flows and password grant. A real Keycloak access token must remain rejected
by the current FastAPI authentication. The realm/client import is compared with the
source, then live user subject, edited configuration and public keys must survive
both identity PostgreSQL and Keycloak restart.

The new identity mapping tests exercise real PostgreSQL PK/FK/unique constraints,
explicit trust/review checks, no email linking, runtime privilege denial and
populated application migration/downgrade/re-upgrade without UUID/data changes.
The historical schema-head/FK assertions are updated only for the additive table;
all seven P0 defect cases and all auth/business assertions remain unchanged.

Artifacts under tests/p3/artifacts are local and ignored. Public discovery/JWKS and
sanitized case/command results can be retained in docs/testing. Never retain tokens,
passwords, private keys, database exports or process environments as evidence.

For constrained cloud hosts, P3_BUILD_OVERLAY may point to a local Compose build
configuration supplying a platform proxy and trusted CA. This does not replace any
runtime test or disable verification. The committed Dockerfile works normally on a
host with standard package/DNS connectivity. Do not fake DNS responses or skip a
failing regression to claim acceptance.

Use `python tests/p3/run.py --identity-only` to rerun P3's 22 integration and three
infrastructure cases after a P3-test correction. It records a separate fresh run in
`artifacts/identity-only`; it does not replace the required full regression run.

For a small isolated host using Docker's `vfs` storage driver, set
`P3_RELEASE_BUILD_CACHE=1` to release unused builder cache after a successful build,
before allocating test containers/databases. This keeps final images and does not
remove containers, database volumes, test cases or assertions. Ensure ample free
disk space and remove only obsolete images created by earlier test attempts.

When container-executed source is unchanged after a host resource failure,
`P3_REUSE_PROJECT_IMAGES=cloud-api-p3-<previous-project-id>` reuses that test project's
images instead of rebuilding. The runner verifies SHA-256 hashes of all executed
Python sources and realm JSON, and checks that application/job image filesystems
match. Stale sources are rejected. All tests, startup and fresh disposable volumes
are still required; only installation outputs are reused. Host run.py drivers are
excluded from the image check because they execute directly from the checkout.
