# Security event coverage and privacy

Event inference is deliberately bounded; response status alone cannot identify every root cause. `timestamp`, generated `request_id`, status, normalized route, method and elapsed milliseconds accompany FastAPI events. Kong supplies status, fixed gateway route, request ID and seconds. Alloy preserves the original Docker RFC3339Nano source timestamp. This avoids presenting old source lines as newly generated events on replay; it does not guarantee exactly-once delivery.

| Event | Source / trigger | Severity / meaning | Rule | Limitation |
| --- | --- | --- | --- | --- |
| http_request | API success or other normal response; gateway access | info / traffic | overview | Aggregate gateway events overlap API events; use service-specific totals |
| token_rejected | Gateway-only JWT401 or API missing/invalid JWT | warning / rejected credentials | JWT rejection spike | Missing, invalid and expired JWT causes are combined |
| identity_unmapped_or_disabled | API existing issuer/sub lookup returns no active mapped user | warning / identity rejected | identity dashboard | Unmapped and disabled intentionally share the same event/response |
| rbac_denied | API 403 outside ownership/security route | warning / authorization denied | dashboard | Admin route is identifiable by route template, not a separate privileged claim |
| ownership_denied | API order/user detail 403 | warning / ownership denial | BOLA spike | Current exact route semantics only |
| rate_limited | Gateway 429 | warning / quota rejected | rate-limit spike | Peer-IP aggregation inherited from P5 |
| webhook_rejected | webhook 4xx except409 | warning / rejected delivery | webhook attacks | Includes malformed/timestamp failures; not exclusively invalid MAC |
| webhook_replayed | authenticated receipt retry | info / safely deduplicated | dashboard only | Benign provider retry is not automatically an attack |
| webhook_conflict | webhook409 | warning / conflicting event ID | webhook attacks | Provider bugs possible |
| ssrf_denied | security route403 | warning / URL policy denial | SSRF spike | Does not mean a fetch occurred; DNS400 is not labeled hostile |
| validation_failed | API422 | warning / invalid input | dashboard | Client mistakes and attacks overlap |
| service_error / upstream_error | API5xx / gateway500,502–504 | error / availability symptom | upstream error spike | Not proof of certificate failure; no active availability probe |
| mtls_verification_failed | Kong bounded in-memory upstream certificate verification error | error / TLS peer rejected | infrastructure dashboard; upstream-error alert remains coarse | Four constant reasons only, explicitly unattributed |
| login_failed | Keycloak LOGIN_ERROR line, reduced to constant fields | warning / failed login | dashboard coverage pending | No username, IP, error text or token retained in Loki; lockout not separately parsed |

## Audit

`audit_logs` already exists in migration0001. P6 does not change schema. Product create/update/deactivate, user administrative changes and order status changes append action, application actor/resource UUID, correlation UUID and schema version. No before/after personal values, free text, IP, browser header or password is copied. `flush`/audit/business effects share one SQL transaction; rollback removes both, audit insert failure prevents business commit. Access-denied events use nontransactional structured logs so they survive business rollback. This is not event sourcing.

Migration job explicitly grants runtime INSERT on audit_logs and USAGE on its sequence, with no SELECT/UPDATE/DELETE. Existing grants are re-applied rather than granting arbitrary future tables. Application users cannot read audit records through an API; there is no new audit endpoint. Authorized operators use separately controlled owner credentials. Database owners and host administrators remain able to modify records; no immutability or tamper-proof claim is made.

## Retention and access

Loki target is7days, with compactor deletion delayed2hours and24-hour index periods; effective physical deletion is delayed and must be measured. Docker json-file rotation is10MiB ×3 per selected service. Audit retention is operator-controlled, suggested90days subject to local policy and incident needs; no destructive purge is automated. Encrypted offline backup, restricted operator access and restore rehearsals are required operational work, not demonstrated privacy compliance. Loki has no built-in auth here and must remain reachable only on the internal observability network. Grafana is loopback-only with generated file-secret credentials. Use an authenticated verified-HTTPS management proxy before remote access.

P6's final implementation marks destination-policy denials at the validator and role denials at the existing RBAC dependency, without altering either decision. A customer denied entry to the SSRF endpoint is therefore RBAC denied, not evidence that destination validation ran. Identity lookup failures use `identity_unmapped_or_disabled`, preserving the existing combined query/response and avoiding account enumeration. The exact distinction between missing mapping and disabled account is intentionally unavailable. Audit writes use inline INSERT without RETURNING, so SELECT privileges are not needed.

Source-specific review: Uvicorn access logs are disabled and exception records lose exception text/tracebacks before server persistence. PostgreSQL P6 logging suppresses SQL statements/details on error; SQLAlchemy DEBUG remains false. Identity-edge and SPA access logs omit query strings, and their error logs are disabled to prevent raw request-line leakage. Kong uses its safe JSON access format and suppresses raw proxy error logs. Keycloak HTTP access logging is explicitly disabled; event logs on the host can retain identity metadata under bounded Docker rotation. Alloy drops non-reviewed raw lines before Loki. Loki's own log level is warning, Grafana query logging is off and its log level warning. These choices reduce diagnostic detail; transport cause and detailed database exceptions require controlled operator probes rather than copying raw exceptions into centralized logs.

Gateway401 is classified as `token_rejected` only when Nginx reports no upstream attempt. Upstream401 remains a generic gateway HTTP observation and the application supplies its precise category. In particular, a missing webhook HMAC must not be counted as a rejected JWT. The safe gateway access record includes only the bounded upstream status string, never upstream URLs, headers or bodies.

## Sanitized upstream TLS failures

`mtls_verification_failed` is emitted only for whitelisted Kong upstream TLS verification messages: SAN mismatch, untrusted issuer/chain, expired certificate and inappropriate EKU. A small tracked OSS log-phase plugin reads OpenResty's bounded128KiB in-memory error ring and writes only constant reasons to stdout; raw proxy error output remains disabled. No body, URL, token, certificate/private key or raw exception is copied. The prefix is checked before request-context text, preventing a URL value from being interpreted as the reason. The plugin does not validate JWTs or change requests/responses/TLS.

The worker error ring can include earlier activity, so these reason events explicitly use `request_id=unattributed`; generic HTTP502 gateway events retain normal correlation IDs. This is reliable evidence that a verification error occurred, not proof of one-to-one request attribution. Ring overflow, batch bounds or another ring reader can lose details; coarse upstream status monitoring remains. Backend inbound handshake failures that never reach HTTP are not separately attributed. No blanket "all TLS errors collected" claim is made.

Application `duration_ms` measures middleware processing until response headers become available; it is not complete browser/network/body-transfer latency. Gateway `duration_seconds` comes from Nginx request time. These are separate measurements and are not interchangeable. Application5xx records use error/failure;4xx use warning/denied, with `event_type` distinguishing validation from authentication/authorization.
