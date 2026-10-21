# Operator response

1. Check Grafana rule state, query errors and Alloy readiness before interpreting an absence of events.
2. Query Loki by service and time window. Use generated request IDs to correlate gateway/API observations; do not paste bearer tokens, signatures, credentials or raw callbacks into tickets.
3. For authorization denials, verify current PostgreSQL roles/ownership through authorized operators. Do not assign roles based on token claims or email.
4. For webhook conflicts, preserve receipts and review the provider event ID/body digest. Never delete receipts to make retries succeed.
5. For SSRF denials or DNS errors, preserve address classification and diagnose resolver/network health separately.
6. For upstream failures, inspect verified TLS enrollment, expiry and service readiness. Do not disable TLS verification or mTLS.
7. If ingestion is broken, inspect Alloy's internal readiness/metrics and Loki limits/disk through authorized management access. Rotate only reviewed logs and recover persistent positions. Do not add request/user/IP labels.
8. Record incident timeline and recovery. A synthetic rule firing does not establish real MTTD/MTTR. Use approved Grafana silences for maintenance when tested; no automated blanket mute is provisioned.

There is no external notification delivery configuration in this repository. Local Grafana evaluation requires an operator or separately approved notification integration.
