import hashlib
import hmac
import json
import time
from datetime import datetime, timezone

from fastapi import APIRouter, Header, HTTPException, Request, status

from app.config import settings

router = APIRouter(prefix="/webhooks", tags=["Webhooks"])

WEBHOOK_SECRET = getattr(settings, "WEBHOOK_SECRET", None)
TIMESTAMP_TOLERANCE_SEC = 300


def _get_webhook_secret() -> str:
    if not WEBHOOK_SECRET:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Webhook secret is not configured",
        )
    return WEBHOOK_SECRET


def _verify_timestamp(timestamp_header: str | None) -> str:
    if not timestamp_header:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing X-Timestamp",
        )

    try:
        request_ts = int(timestamp_header)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid X-Timestamp",
        )

    now_ts = int(datetime.now(timezone.utc).timestamp())

    if abs(now_ts - request_ts) > TIMESTAMP_TOLERANCE_SEC:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Webhook timestamp expired",
        )

    return timestamp_header


def _verify_signature(raw_body: bytes, timestamp: str, signature_header: str | None) -> bool:
    if not signature_header:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing X-Signature",
            headers={"WWW-Authenticate": 'HMAC realm="webhook"'},
        )

    if not signature_header.startswith("sha256="):
        return False

    received_hex = signature_header[len("sha256="):]
    signed_payload = timestamp.encode() + b"." + raw_body

    expected = hmac.new(
        key=_get_webhook_secret().encode(),
        msg=signed_payload,
        digestmod=hashlib.sha256,
    ).hexdigest()

    return hmac.compare_digest(expected, received_hex)


@router.post(
    "/receive",
    status_code=status.HTTP_200_OK,
    summary="Receive signed webhook",
)
async def receive_webhook(
    request: Request,
    x_signature: str | None = Header(default=None, alias="X-Signature"),
    x_timestamp: str | None = Header(default=None, alias="X-Timestamp"),
):
    """
    Webhook security flow:
    1. Require X-Timestamp.
    2. Reject old timestamps to prevent replay attacks.
    3. Verify HMAC-SHA256 over: X-Timestamp + "." + raw_body.
    4. Process event only after signature verification.
    """
    timestamp = _verify_timestamp(x_timestamp)
    raw_body = await request.body()

    if not _verify_signature(raw_body, timestamp, x_signature):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid webhook signature",
        )

    try:
        payload = json.loads(raw_body)
    except json.JSONDecodeError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid JSON body",
        )

    event_type = payload.get("event")
    result = _handle_event(event_type, payload)

    return {
        "received": True,
        "event": event_type,
        "message": result,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


def _handle_event(event_type: str | None, payload: dict) -> str:
    handlers = {
        "payment.success": _on_payment_success,
        "payment.failed": _on_payment_failed,
        "order.shipped": _on_order_shipped,
    }

    handler = handlers.get(event_type)
    if not handler:
        return f"Event '{event_type}' received but no handler is registered"

    return handler(payload)


def _on_payment_success(payload: dict) -> str:
    order_id = payload.get("order_id")
    return f"Payment succeeded for order {order_id}"


def _on_payment_failed(payload: dict) -> str:
    order_id = payload.get("order_id")
    return f"Payment failed for order {order_id}"


def _on_order_shipped(payload: dict) -> str:
    order_id = payload.get("order_id")
    tracking_no = payload.get("tracking_number")
    return f"Order {order_id} shipped with tracking {tracking_no}"


@router.get(
    "/test-signature",
    summary="[DEV] Generate test webhook signature",
)
def generate_test_signature(event: str = "payment.success", order_id: str = "test-123"):
    """
    Development helper only.
    Disabled when DEBUG=False.
    """
    if not settings.DEBUG:
        raise HTTPException(status_code=404, detail="Not found")

    timestamp = str(int(time.time()))
    body = json.dumps(
        {"event": event, "order_id": order_id},
        separators=(",", ":"),
    ).encode()

    signed_payload = timestamp.encode() + b"." + body

    signature = "sha256=" + hmac.new(
        key=_get_webhook_secret().encode(),
        msg=signed_payload,
        digestmod=hashlib.sha256,
    ).hexdigest()

    return {
        "instructions": "Use these headers and body to test POST /webhooks/receive",
        "headers": {
            "Content-Type": "application/json",
            "X-Signature": signature,
            "X-Timestamp": timestamp,
        },
        "body": body.decode(),
    }