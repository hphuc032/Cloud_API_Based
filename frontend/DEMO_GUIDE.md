# P5 disposable security demonstration

Use the OIDC candidate with explicit operator-reviewed mappings and disposable users/data. Read [P5 results](../docs/testing/p5-results.md) before presenting acceptance claims. No demo passwords, administrator credentials or signing keys are embedded in the bundle. The main automated demonstration is `python3 tests/p5/run.py --focus browser`.

The browser signs in at Keycloak with Authorization Code + S256 PKCE. Application role and active status come from `/auth/me` and PostgreSQL. Tokens remain in memory. Select **Security Center** through the navigation after login. The existing callback goes to the application home; an initial deep-link navigation may return home after SSO, so select the page again rather than assuming the original route is restored.

Use a separately built `VITE_SECURITY_LAB=true` frontend only in an authorized disposable lab. BOLA fixture inputs, webhook forging/retry and rate bursts are hidden in the normal build. Supply customer A, customer B and staff mappings without granting roles from token claims.

| Scenario | Steps | Inspect the observed response |
| --- | --- | --- |
| Missing/invalid token | Select Missing access token and Invalid access token | Kong 401; intentional probes keep the legitimate UI session |
| Unauthorized administration | Sign in as a customer; select Check admin authorization | Actual 403; no destructive admin action is used |
| BOLA | Enter customer B's disposable order UUID while logged in as customer A; select Check BOLA | Actual 403 with ownership enforced by FastAPI |
| HMAC forgery | Select Webhook forgery | Actual 403 for a fresh timestamp and forged MAC |
| Webhook retry | Generate a private short-lived delivery file using the operator CLI below; paste exact body, timestamp and signature; submit twice | Two actual 200 stored acknowledgements, identical JSON and second replay header true; this is idempotent handling, not a second business effect |
| SSRF metadata | Sign in as staff/admin; select SSRF metadata validation | Actual 403 for metadata address; customer button is disabled and API role checks remain authoritative |
| SQL-shaped input | Select SQL-shaped input | Actual 422 for invalid UUID-shaped category input; the read-only probe does not execute injected SQL |
| Rate limit | Select Rate burst (up to 65 public reads) | Stops on actual 429 or network failure; inspect reported limiter layer and Retry-After. Prior traffic may exhaust the quota earlier |
| Security headers | Select Inspect security headers | Actual response headers; production HTML also has its own browser-compatible CSP |
| Invalid client certificate | Run the isolated P2 socket and host checks | TLS failure before an application HTTP response, or verified Kong 502 for a bad upstream server certificate; browser JavaScript cannot supply arbitrary client certificates |

Offline disposable signing:

```sh
APP_ENV=test P0_ISOLATED=1 python3 tests/p5/lab.py --disposable-lab \
  --secret-file /path/to/disposable/webhook_secret --output /tmp/new-lab-delivery.json
```

The CLI writes a new mode-0600 file and performs no network request. Paste its fields without editing the body. The frontend preserves exact string bytes, including boundary whitespace; no browser-side signing secret is needed. Use fresh timestamps within the configured tolerance and fresh event IDs for unrelated events. Keep the file private and remove it after the lab. Never commit it.

Reload to demonstrate SSO recovery without stored bearer tokens, then logout and verify the exact allowed return URL. Automated browser checks also exercise invalid state/nonce and IdP outages. Inspect real Loki rejection logs; Monitoring shows no fabricated numbers and links only to an explicitly configured HTTPS Grafana URL.

Kong API quotas do not cover the Keycloak login route. Keycloak's own brute-force controls are separately tested. SSRF success still needs functioning real DNS; the validator never fetches remote content. Rate bursts can affect other users sharing the same proxy peer, so never run them against a shared production gateway. Access tokens may remain valid until expiry after logout; database deactivation still denies subsequent requests. Review [design and limitations](../docs/security/p5-design.md).
