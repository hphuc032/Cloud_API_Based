"""Allowlisted telemetry: never serialize requests, exceptions, tokens or bodies."""
import contextvars
import json
import logging
import time
import uuid
from datetime import datetime, timezone

request_context = contextvars.ContextVar("security_request", default=None)
security_context = contextvars.ContextVar("security_reason", default=None)

def mark(event):
    context = security_context.get()
    if context is not None and event in EVENTS:
        context["event"] = event

logger = logging.getLogger("florasecure.security")
logger.setLevel(logging.INFO)
logger.propagate = False
if not logger.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(message)s"))
    logger.addHandler(handler)

EVENTS = {"http_request", "token_rejected", "identity_unmapped_or_disabled",
          "rbac_denied", "ownership_denied", "webhook_rejected", "webhook_replayed",
          "webhook_conflict", "ssrf_denied", "validation_failed", "service_error"}

def emit(event_type, *, status_code, route="unmatched", method="OTHER", duration_ms=0,
         request_id=None):
    if event_type not in EVENTS:
        raise ValueError("Unknown event type")
    # All variable strings are framework templates or generated IDs, never client values.
    record = dict(timestamp=datetime.now(timezone.utc).isoformat(), service="fastapi",
                  level="error" if status_code >= 500 else "warning" if status_code >= 400 else "info",
                  event_type=event_type, event_outcome="failure" if status_code >= 500 else "denied" if status_code >= 400 else "success",
                  request_id=request_id or str(uuid.uuid4()), method=method,
                  route=route, status_code=status_code, duration_ms=round(duration_ms, 3))
    logger.info(json.dumps(record, separators=(",", ":")))


def audit(db, actor_id, action, resource_type, resource_id):
    """Participate in the caller's transaction; no independent commit or fail-open."""
    from app.models.audit_log import AuditLog
    context = request_context.get()
    from sqlalchemy import insert
    # Inline INSERT avoids ORM RETURNING, which would require audit SELECT grants.
    db.execute(insert(AuditLog.__table__).inline().values(
        user_id=actor_id, action=action, resource_type=resource_type,
        resource_id=resource_id, request_id=uuid.UUID(context) if context else None,
        detail={"schema_version": 1}))
