# Provisioned detection rules

Source of truth: `monitoring/p6-grafana/alerting/security.json`. Six lab rules evaluate every10seconds with a1minute lookback and30second pending period. Severity warning, phase p6, environment lab. Loki datasource UID `florasecure-loki`. NoData stays NoData and query errors become Error; neither silently implies healthy. `or vector(0)` returns zero when no matching events exist but the query succeeds. Missing-service telemetry requires a separate heartbeat/probe and is not implemented.

| UID suffix | JSON event filter | Count greater than | Response |
| --- | --- | ---: | --- |
| jwt-rejections | token_rejected |5| Check gateway-only vs API rejection; investigate spike without exporting tokens |
| webhook-attacks | webhook_rejected or webhook_conflict |3| Verify provider configuration/clock/keys and receipt conflicts |
| ownership-denials | ownership_denied |3| Review application actor through authorized audit path and affected route |
| ssrf-denials | ssrf_denied |3| Review client intent; preserve deny policy |
| rate-limits | rate_limited |5| Distinguish shared-peer quota and abuse; do not relax JWT |
| upstream-errors | upstream_error |3| Check backend health, expiry/enrollment, upstream availability |

Exact LogQL, evaluator thresholds and annotations are provisioned in the JSON file. Gateway-only JWT401 and backend token-validation failures are classified separately; upstream webhook401 is not a gateway JWT rejection. Counts remain event observations, not independent incidents or users. Production thresholds require measured baselines and request-ID deduplication if distinct-event counts are needed. False positives include integration errors, shared proxy peers, expired sessions, provider retries/configuration mistakes and maintenance. There are no configured external notification credentials, routes or delivery assertions. Grafana defaults and external delivery are not an incident-response guarantee.

Dashboards are automatically provisioned under Security with stable UIDs `florasecure-overview`, `florasecure-identity`, `florasecure-attacks`, `florasecure-infrastructure`. Missing Keycloak/availability/storage/explicit transport telemetry is stated on dashboards. They contain real LogQL queries, no hardcoded live statistics. Latency distributions, top gateway route rejection rates, active probes and disk metrics remain future work.

Acceptance recovery exercised all six rules through real events and the actual Grafana engine, including pending/firing/recovery. The five additional rules crossed their unchanged thresholds with observed counts webhook9, ownership8, SSRF8, rate-limit12 and upstream8. Exact LogQL, UTC engine evaluations and scope are in [recovery alert evidence](../testing/p6-recovery-alerts.json). This verifies local evaluation only; external notification delivery, grouping/silences and exhaustive missing-data fault injection remain untested.
