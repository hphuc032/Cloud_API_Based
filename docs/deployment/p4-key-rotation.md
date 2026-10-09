# P4: Keycloak signing keys and Kong OSS

Pinned Kong OSS 3.8 supports native JWT `key_claim_name=kid` (including the JWT
header), RS256 public-key credentials, mandatory `exp` and `maximum_expiration=300`.
FastAPI retains independent full OIDC verification. No Enterprise OIDC plugin,
symmetric issuer credential, administrative gateway API or Docker socket is used.

The `kong-keys` one-shot job uses only the configured public HTTPS issuer, trusted
CA and exact CORS origins. It cannot read either database or application signing
secrets. The shared gateway volume contains public RSA keys and route policy only;
Kong mounts it read-only. Initial generation happens before Kong starts and invalid
configuration prevents startup. No periodic unsafe auto-reload is claimed.

Set the following shell function to the **reviewed candidate** project and existing
runtime environment; do not substitute a production project until acceptance and
change approval. Keep the same secrets, PKI, stable issuer and exact SPA origins.

```sh
dc() { docker compose --env-file docker/.env -p "$P4_PROJECT" \
  -f docker/docker-compose.yml -f docker/p4-compose.yml "$@"; }
```

For each refresh, render separately, validate with the pinned actual Kong binary,
approve the exact parsed bytes, promote atomically, reload and verify HTTPS:

```sh
digest=$(dc run --rm --no-deps -T kong-keys python -m deployment.kong_jwks \
  --output /gateway/kong.json --candidate)
dc exec -T kong kong config parse /gateway/kong.candidate.json >/dev/null
dc run --rm --no-deps -T kong-keys python -m deployment.kong_jwks \
  --output /gateway/kong.json --promote-digest "$digest"
dc exec -T kong kong reload
# Use the deployment's published HTTPS endpoint and verified edge CA.
curl --cacert "$PKI_DIR/trust/edge-ca.pem" https://localhost:8443/health
```

Run each command with error checking (`set -e` for a reviewed script). A concurrent
changed candidate fails digest promotion. Failed JWKS retrieval never replaces the
active file; failed parse must not be promoted. Promotion preserves the previous
public configuration. Keep one operator/change lock across render/parse/promote/
reload: simultaneous key/route updates are unsupported. Digest approval proves
byte identity with the parsed file, not external authorization.

## Planned rotation

1. At the private Keycloak administrator interface, add a new RS256 signing
   provider with **enabled=true, active=false**. Never transfer private keys to
   Kong. Confirm the new public `kid` appears in verified JWKS.
2. Synchronize and parse/promote/reload Kong **before activating issuance**. Confirm
   existing tokens still pass. FastAPI learns the published key on a bounded
   cache refresh or an unknown-kid attempt; allow its five-second retry interval.
3. Activate the new higher-priority signing provider. Keep the old provider enabled
   and passive. Verify a genuine newly issued access token at both Kong and the
   backend, and verify old unexpired tokens during overlap.
4. For a normal production rotation, overlap for at least **300 seconds plus the
   60-second JWKS cache TTL and clock/deployment margin**, measured from the last
   old-key issuance. Confirm refresh now issues only the new key.
5. Disable/remove the old signing provider so verified JWKS no longer publishes it.
   Repeat parse/promote/reload. Kong must reject its `kid` before upstream handling.
   Backend trust expires within TTL. For urgent retirement, restart the backend
   to clear all process caches, then verify old tokens fail and new tokens pass.

Disposable tests intentionally retire an **unexpired** old token and use backend
restart to prove emergency trust removal, rather than pretending to wait out a
normal production overlap. The normal waiting requirement above remains mandatory.
Unknown new kids fail closed at Kong until synchronization; successful backend
dynamic refresh does not by itself update Kong.

If reload fails, restore the previous public configuration and parse/reload only
after review. **Do not restore compromised keys.** For an ordinary noncompromise
configuration rollback:

```sh
dc run --rm --no-deps -T kong-keys python -m deployment.kong_jwks \
  --output /gateway/kong.json --rollback
dc exec -T kong kong config parse /gateway/kong.json >/dev/null
dc exec -T kong kong reload
```

Review rollback key validity and issuer continuity. Availability may fail closed
on an expired JWKS cache during an IdP outage. No stale-key fail-open or legacy
authentication fallback is introduced.
