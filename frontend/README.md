# FloraSecure frontend

React/Vite/Tailwind with Keycloak Authorization Code + PKCE S256. Identity tokens stay in memory; PostgreSQL supplies application roles through the mapped `/auth/me` profile. The P5 candidate adds a strict browser CSP, actual Security Center response probes and an optional disposable lab build. See [demo guide](DEMO_GUIDE.md) and the root README for the complete HTTPS/mTLS stack.

```sh
npm ci
npm run build
```

Development needs the reviewed HTTPS IdP origin (`VITE_OIDC_URL`), exact registered frontend redirects/origin, `VITE_TLS_CERT`/`VITE_TLS_KEY`, an HTTPS `API_PROXY_TARGET`, and `NODE_EXTRA_CA_CERTS` for the gateway CA. Keep proxy certificate verification enabled. `npm run dev` uses Vite's development nonce policy; it is not the production serving boundary. Never commit certificates' private keys, tokens or runtime secret files. The default IdP/proxy values are development candidates and must be reviewed for each deployment.

For production-style browser validation, build assets and use `docker/render_spa.py` plus `docker/p5-compose.yml` after the P4 overlay. Supply dedicated SPA TLS files, the public gateway CA, exact IdP origin, rendered Nginx configuration and dist directory. Public generated dist directories must be readable as 0755 and files as 0644 by the Nginx worker; preserve private key permissions. The isolated P5 browser driver prepares those public permissions automatically. Static access logs omit query values, including OAuth callback code/state.

Compile `VITE_SECURITY_LAB=true` only for authorized disposable demonstrations. The browser receives temporary MACs from an operator-held key, never the key itself. Leave `VITE_GRAFANA_URL` unset unless a reviewed HTTPS monitoring URL exists. Frontend build success and UI labels alone do not establish security acceptance; use [P5 test evidence](../docs/testing/p5-results.md).
