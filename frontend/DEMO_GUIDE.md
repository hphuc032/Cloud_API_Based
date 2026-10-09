# P4 browser demonstration

Use only a disposable candidate with reviewed explicit account mappings. There
are no committed demo passwords or embedded client secrets. P4 is not production
cutover approval; read `docs/testing/p4-results.md` first.

1. Start the candidate described in `docs/deployment/p4-cutover.md`. Configure
   exact HTTPS realm redirect/web origins and `VITE_OIDC_URL`. The issuer must be
   stable and reachable from browser, FastAPI and the public-key sync job.
2. Provide verified frontend TLS certificate/key paths and trust the generated
   public development edge/identity CAs only after fingerprint review. Vite's API
   proxy must trust the gateway CA via `NODE_EXTRA_CA_CERTS`; keep `secure=true`.
3. Open the configured HTTPS frontend `/login` and select Sign in. Credentials are
   entered at Keycloak. The adapter exchanges a code using S256 PKCE, verifies
   state/nonce and fetches the mapped application profile. Tokens remain in memory.
4. Use customer/staff/admin **database roles** through explicitly reviewed mapping
   fixtures. Show product reads, permitted product writes, own versus another
   customer's orders, order status policy, profile and existing admin operations.
   Keycloak role claims and forged identity headers do not grant application roles.
5. Reload: recover identity through Keycloak SSO, with no persistent access/refresh
   token. Show legacy `fs_*` entries removed. Do not display full JWTs or passwords.
6. Logout: POST to Keycloak, then return to the exact allowed `/login`. A reload
   should remain signed out. Session expiration/refresh failure clears the UI;
   initialization outage shows an error and Reload sign-in allows a later retry.
7. Security Center still exercises HMAC webhook and SSRF validation. Development
   HMAC-signature helper is disabled; use a separately authorized trusted webhook
   sender. The rate-limit demonstration sends six public reads; these six alone
   need not exhaust the global 60/minute policy. Automated tests exhaust it and
   prove 429 without changing the policy.
8. Verify Loki receives backend logs without secrets/full tokens. Do not infer
   security acceptance from UI alone; use the automated candidate and legacy
   regression reports.

SSRF success requires real public DNS. Do not add fixed public DNS answers or
weaken the validator for a demonstration. Access-token revocation after logout is
bounded by token expiry; application `is_active=false` denies on the next request.
No BFF, HttpOnly application session, WAF or later-phase feature is claimed.
