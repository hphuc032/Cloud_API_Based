# P7 attack-to-control matrix

Only disposable authorized lab services. Actual case-level outcomes are in
[p7-case-results.json](../testing/p7-case-results.json); request/status/event records,
rule observations, TLS and DB assertions are in
[p7-runtime-evidence.json](../testing/p7-runtime-evidence.json). Statuses refer to executed case assertions and the scoped evidence below;
AS08 remains BLOCKED by deferred real-DNS acceptance. Final outcome is in [P7 results](../testing/p7-results.md).
Positive tokens are actual Keycloak code+PKCE tokens. Trusted-signer negative
claims and intentionally broken signatures are attack fixtures only.

| ID | Status | Preconditions / request | Expected defense / evidence | Actual executing cases |
|---|---|---|---|---|
|AS01|PASS|Anonymous GET protected auth/me|401 at Kong; no upstream; token_rejected through Alloy/Loki|P7 test_as01_missing_token; P6 gateway boundary/privacy|
|AS02|PASS|Malformed signature with actual kid/claim envelope|401 gateway and no legacy fallback|P7 test_as02_invalid_signature; P4 test_gateway_rejects_or_backend_finishes_validation invalid-signature/unknown-kid|
|AS03|PASS|Expired/missing time, wrong issuer/audience, HS256, ID/refresh token as access|401; gateway signature/exp subset, independent backend full OIDC; wrong issuer/aud can reach backend|P7 test_as03_gateway_is_not_complete_oidc; P4 independent_claim_validation and gateway_rejects_or_backend_finishes_validation parametrizations|
|AS04|PASS|Mapped customer PATCH another user role=admin|403, unchanged SQL role; rbac_denied in Loki|P7 test_as04_customer_cannot_mutate_admin; existing P4 DB role/is_active authority|
|AS05|PASS|Customer B GET customer A order|403 per current policy; no order fields; ownership_denied|P7 test_as05_bola; P4 own/list/status matrix|
|AS06|PASS|Public webhook route, valid body but forged HMAC|403, no receipt/business effect; webhook_rejected|P7 test_as06_forgery_no_receipt; P5 missing/tampered/time/body/size negatives|
|AS07|PASS|Real signed lab event, identical retries, same ID/different body; eight concurrent local requests|200 replay header/same ack, one receipt/handler; conflict409; atomic rollback|P7 test_as07_network_replay_and_conflict; P5 test_concurrent_duplicates_real_postgres/test_failed_operation_rolls_back_receipt_and_effect; P6 audit transaction tests|
|AS08|BLOCKED|Staff submit IPv4/IPv6/mapped loopback, RFC1918, link-local, metadata; deterministic mixed DNS|403 literal policy; mixed answers fail closed; ssrf_denied Loki; no download|P7 test_as08_validator_denies_nonpublic; P5 address/parser/mixed DNS parametrizations. Actual public DNS staff/admin acceptance NOT EXECUTED by user instruction|
|AS09|PASS|Controlled burst of protected/public requests, spoofed forwarding headers|Exact existing quotas reached;429 and Retry-After; rate_limited ingested|P5 test_pre_auth_throttle_rejects_forwarding_header_spoofing; P6 test_gateway_rate_limit_collected/test_four_additional_rule_transitions; P4 global limiter|
|AS10|PASS|Admin GET user with harmless SQL-shaped UUID strings|422 before business query; fixture count unchanged; validation_failed|P7 test_as10_sql_shaped_uuid_no_business_effect. This covers UUID input, not every SQL injection class|
|AS11|PASS|Null/invalid product price, null/invalid role, invalid UUID, malformed signed JSON|Controlled400/422, no500 or partial update/receipt|P7 test_as11_input_no_unhandled_500; P5 null/adjacent/nonfinite/role/object/schema parametrizations|
|AS12|PASS|Missing/untrusted/expired/unenrolled/wrong-EKU TLS client and wrong SAN/issuer server|TLS failure before HTTP; enrolled client200; actual Kong peer rejection502|P2 test_bad_client_is_tls_failure_not_http_auth, valid_mtls_is_http_200; all16 host certificate/enrollment/rotation checks. Four-reason Loki evidence inherited unchanged from P6 when not freshly sampled|
|AS13|PASS|Selected actual attacks + provisioned queries/rules|Request correlation, event collection and query result, actual pending/firing/recovery; privacy/audit guarantees scoped|P7 AS01/03–08/10 real request IDs; P6 all24cases and lifecycle; P7 monitoring recovery|

The P7 new suite records PASS only after HTTP/SQL/Loki assertions have completed.
Failed assertions remain failures in JUnit even if a prior step produced a log.
Initial P7 seed error expected nonexistent order_created telemetry; it was corrected
to the actual http_request event and SQL ownership, not by changing application logs.
Full and focused reruns remain separate evidence; no repeated execution is counted
as a new vulnerability. No production calls, arbitrary external scanning, destructive
SQL payloads, HMAC key exposure or actual SSRF fetching occur.

The webhook handler is a simulated acknowledgement. A single durable receipt is
not evidence of a real payment settlement. The concurrent P5 instrumentation counts
the actual in-process handler plus real PostgreSQL arbitration in an isolated app;
P7's network replay confirms the deployed service acknowledgement/receipt contract.
Kong JWT is not complete OIDC; backend mTLS bypass tests use an enrolled client.
External alert notification delivery, missing-data/silence incident handling and
complete adversarial coverage remain unexecuted, as documented in the final matrix.
