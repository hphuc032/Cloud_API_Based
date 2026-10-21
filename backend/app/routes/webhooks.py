"""Raw-body HMAC plus atomic, provider-scoped idempotent acknowledgements."""
import hashlib
import hmac
import json
import re
import time
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, Header, HTTPException, Request, Response
from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator
from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session
from app.config import settings
from app.database.session import get_db
from app.models.webhook_receipt import WebhookReceipt

router = APIRouter(prefix='/webhooks', tags=['Webhooks'])
WEBHOOK_SECRET = settings.WEBHOOK_SECRET

class WebhookEvent(BaseModel):
    model_config = ConfigDict(strict=True, extra='allow')
    event: str = Field(min_length=1, max_length=128, pattern=r'^[A-Za-z0-9][A-Za-z0-9._-]*$')
    event_id: str | None = Field(default=None, min_length=1, max_length=200, pattern=r'^[A-Za-z0-9][A-Za-z0-9._:-]*$')
    order_id: str | None = Field(default=None, min_length=1, max_length=255)
    tracking_number: str | None = Field(default=None, min_length=1, max_length=255)

    @model_validator(mode='after')
    def known_event_structure(self):
        if self.event in ('payment.success','payment.failed','order.shipped') and not self.order_id:
            raise ValueError('Known events require order_id')
        return self


def _get_webhook_secret():
    if not WEBHOOK_SECRET:
        raise HTTPException(503, 'Webhook temporarily unavailable')
    return WEBHOOK_SECRET


def _verify_timestamp(timestamp_header):
    if not timestamp_header:
        raise HTTPException(401, 'Missing X-Timestamp')
    if not re.fullmatch(r'(?:0|[1-9][0-9]{0,11})', timestamp_header):
        raise HTTPException(403, 'Invalid X-Timestamp')
    now = int(datetime.now(timezone.utc).timestamp())
    if abs(now-int(timestamp_header)) > settings.WEBHOOK_TIMESTAMP_TOLERANCE:
        raise HTTPException(403, 'Webhook timestamp expired')
    return timestamp_header


def _verify_signature(raw_body, timestamp, signature_header):
    if not signature_header:
        raise HTTPException(401, 'Missing X-Signature', headers={'WWW-Authenticate':'HMAC realm="webhook"'})
    if not re.fullmatch(r'sha256=[0-9a-f]{64}', signature_header):
        return False
    keys = [_get_webhook_secret()]
    now = int(datetime.now(timezone.utc).timestamp())
    start, end = settings.WEBHOOK_PREVIOUS_START, settings.WEBHOOK_PREVIOUS_UNTIL
    if (settings.WEBHOOK_PREVIOUS_SECRET and 0 < end-start <= 900 and start <= now < end):
        keys.append(settings.WEBHOOK_PREVIOUS_SECRET)
    valid = False
    for key in keys:
        expected = hmac.new(key.encode(),timestamp.encode()+b'.'+raw_body,hashlib.sha256).hexdigest()
        valid |= hmac.compare_digest(expected,signature_header[7:])
    return valid


def _object_pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('Duplicate JSON member')
        result[key] = value
    return result


def _invalid_constant(value):
    raise ValueError('Non-finite JSON number')


@router.post('/receive', summary='Receive signed webhook')
async def receive_webhook(request: Request, response: Response,
    x_signature: str | None = Header(default=None,alias='X-Signature'),
    x_timestamp: str | None = Header(default=None,alias='X-Timestamp'),
    db: Session = Depends(get_db)):
    timestamp = _verify_timestamp(x_timestamp)
    length = request.headers.get('content-length')
    if length and (not length.isdecimal() or len(length)>12):
        raise HTTPException(400, 'Invalid Content-Length')
    if length and int(length)>settings.WEBHOOK_MAX_BODY_BYTES:
        raise HTTPException(413, 'Webhook body too large')
    raw = bytearray()
    async for chunk in request.stream():
        raw.extend(chunk)
        if len(raw)>settings.WEBHOOK_MAX_BODY_BYTES:
            raise HTTPException(413, 'Webhook body too large')
    if not _verify_signature(bytes(raw),timestamp,x_signature):
        raise HTTPException(403, 'Invalid webhook signature')
    try:
        payload = json.loads(raw,object_pairs_hook=_object_pairs,parse_constant=_invalid_constant)
        if not isinstance(payload,dict):
            raise ValueError('JSON object required')
        event = WebhookEvent.model_validate(payload)
        canonical = json.dumps(payload,sort_keys=True,separators=(',',':'),ensure_ascii=True,allow_nan=False).encode()
    except (ValueError,TypeError,UnicodeError,RecursionError,ValidationError):
        raise HTTPException(400, 'Invalid webhook event') from None
    digest = hashlib.sha256(canonical).hexdigest()
    # Preserve older senders without IDs, but stable provider event_id is preferred.
    identity = 'id:'+event.event_id if event.event_id else 'body-sha256:'+digest
    provider = settings.WEBHOOK_PROVIDER  # fixed by deployment, never a caller header
    try:
        with db.begin():
            reserved = db.execute(insert(WebhookReceipt).values(provider=provider,event_id=identity,
                payload_sha256=digest).on_conflict_do_nothing().returning(WebhookReceipt.event_id)).scalar_one_or_none()
            if reserved is None:
                receipt = db.execute(select(WebhookReceipt).where(WebhookReceipt.provider==provider,
                    WebhookReceipt.event_id==identity)).scalar_one()
                if receipt.payload_sha256!=digest:
                    raise HTTPException(409, 'Event ID conflicts with an existing payload')
                if receipt.response is None:
                    raise HTTPException(503, 'Webhook acknowledgement unavailable')
                result = receipt.response
                response.headers['X-Webhook-Replayed'] = 'true'
            else:
                # Current handlers acknowledge simulations only. Future DB effects
                # must use THIS session/transaction after successful reservation.
                result = {'received':True,'event':event.event,'message':_handle_event(event.event,payload,db),
                          'timestamp':datetime.now(timezone.utc).isoformat()}
                db.execute(update(WebhookReceipt).where(WebhookReceipt.provider==provider,
                    WebhookReceipt.event_id==identity).values(response=result))
                response.headers['X-Webhook-Replayed'] = 'false'
        return result
    except SQLAlchemyError:
        db.rollback()
        raise HTTPException(503, 'Webhook temporarily unavailable') from None


def _handle_event(event_type: str | None, payload: dict, db: Session | None = None) -> str:
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
