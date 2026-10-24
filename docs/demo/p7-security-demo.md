# P7 security demonstration

Use only a new disposable P7 lab. The test runner tears the lab down after capture;
its JSON evidence can be replayed in a presentation, but is not a live deployment.
No live-customer traffic, production credentials or destructive payloads are allowed.
Build `VITE_SECURITY_LAB=true` only for an authorized disposable UI demonstration;
never place a webhook secret or an IdP admin password in the browser.

1. Show the [trust boundaries](../security/p7-final-assessment.md) and live project
   networks: separate app/identity DBs, no DB ports, Kong HTTPS and backend mTLS.
2. Use the browser suite's real Keycloak login/PKCE flow, profile, refresh and logout.
   Explain current DB roles rather than decoding a token to infer privilege.
3. Create/read a customer's order; compare its SQL owner UUID and application profile.
4. As customer attempt user administration and another customer's known lab order.
   Show actual403 and correlated `rbac_denied` / `ownership_denied` Loki observations.
5. Send invalid HMAC, then submit the same legitimate lab delivery twice; show403,
   one durable receipt and replay header, then conflicting payload409. P5's eight
   concurrent local deliveries prove one simulated handler invocation; this is no
   real payment/fulfillment integration.
6. As staff submit loopback/private/metadata URLs; show403 plus `ssrf_denied`.
   Explain this endpoint validates URLs/DNS and never downloads content. Real public
   DNS success is deferred, not demonstrated by deterministic DNS tests.
7. Run the controlled P5/P6 gateway burst in the fresh lab; show429 and Loki event,
   unchanged peer-IP quota and failed forwarded-header spoofing.
8. Show P2 actual TLS socket negatives versus valid enrolled client200. A browser401
   is authentication failure after TLS, not evidence of failed mutual TLS.
9. Query four provisioned Grafana dashboards and trace a generated request ID at
   Kong and FastAPI. Never display tokens, callback codes, bodies or private keys.
10. Run the P6 rule experiment inside the lab; show actual inactive/pending/firing/
    recovery snapshots. External email/webhook notification delivery is not claimed.
11. Show paired DB restore with fresh code tokens, unchanged user/order UUIDs and
    unchanged authorization, then the release matrix and remaining blockers.

Reproducible entry points and cleanup are in [the deployment guide](../deployment/p7-reproducibility.md).
Every claim must link to [case-level evidence](../testing/p7-case-results.json),
[scenario request/result records](../testing/p7-runtime-evidence.json) or unchanged
P6 retention evidence. Do not display a hardcoded PASS badge as live security state.
