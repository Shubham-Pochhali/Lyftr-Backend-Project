from sqlalchemy import text
import hashlib
import hmac
from datetime import datetime, timezone
from typing import Optional

from fastapi import (
    FastAPI,
    Depends,
    HTTPException,
    Request,
    status,
    Query,
)
from fastapi.responses import JSONResponse, PlainTextResponse
from fastapi.exceptions import RequestValidationError
from pydantic import BaseModel, Field, field_validator

from sqlalchemy.orm import Session

from .config import settings
from .storage import init_db, get_db, insert_message, list_messages, get_stats
from .logging_utils import logging_middleware, iso_now
from .metrics import inc_webhook_result, render_metrics


app = FastAPI(title="Lyftr Backend Assignment")

# Attach logging middleware
app.middleware("http")(logging_middleware)


# ---------- Pydantic Models ----------


class WebhookPayload(BaseModel):
    message_id: str = Field(min_length=1)
    from_: str = Field(alias="from")
    to: str
    ts: str
    text: Optional[str] = Field(default=None, max_length=4096)

    @field_validator("from_", "to")
    @classmethod
    def validate_msisdn(cls, v: str) -> str:
        # E.164-like: + then digits only
        if not v.startswith("+") or not v[1:].isdigit():
            raise ValueError("must start with '+' followed by digits")
        return v

    @field_validator("ts")
    @classmethod
    def validate_ts(cls, v: str) -> str:
        # expecting ISO-8601 with Z suffix
        if not v.endswith("Z"):
            raise ValueError("ts must be ISO-8601 UTC with 'Z' suffix")
        try:
            datetime.fromisoformat(v.replace("Z", "+00:00"))
        except ValueError:
            raise ValueError("invalid ISO-8601 timestamp")
        return v


class MessagesResponseItem(BaseModel):
    message_id: str
    from_: str = Field(alias="from")
    to: str
    ts: str
    text: Optional[str]


class MessagesResponse(BaseModel):
    data: list[MessagesResponseItem]
    total: int
    limit: int
    offset: int


# ---------- Startup ----------


@app.on_event("startup")
def on_startup() -> None:
    # initialize DB schema
    init_db()


# ---------- Helpers ----------


def compute_signature(secret: str, raw_body: bytes) -> str:
    return hmac.new(
        key=secret.encode("utf-8"),
        msg=raw_body,
        digestmod=hashlib.sha256,
    ).hexdigest()


def is_ready(db: Session | None = None) -> tuple[bool, str]:
    if not settings.WEBHOOK_SECRET:
        return False, "WEBHOOK_SECRET not set"
    if db is None:
        return True, "ok"
    # Check DB reachable
    try:
        db.execute(text("SELECT 1"))
        
    except Exception as e:
        return False, f"DB error: {e}"
    return True, "ok"


# ---------- Exception handler to count validation errors ----------


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    # Mark this as validation_error for webhook metrics
    if request.url.path == "/webhook":
        inc_webhook_result("validation_error")
        # enrich logs
        request.state.log_extra = getattr(request.state, "log_extra", {})
        request.state.log_extra.update(
            {
                "result": "validation_error",
            }
        )
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"detail": exc.errors()},
    )


# ---------- Endpoints ----------


@app.get("/health/live")
def health_live():
    # always 200 once running
    return {"status": "ok"}


@app.get("/health/ready")
def health_ready(db: Session = Depends(get_db)):
    ok, msg = is_ready(db)
    if not ok:
        raise HTTPException(status_code=503, detail=msg)
    return {"status": "ok"}


@app.post("/webhook")
async def webhook(
    request: Request,
    db: Session = Depends(get_db),
):
    # Signature check first using raw body
    raw_body = await request.body()
    x_sig = request.headers.get("X-Signature")

    if not settings.WEBHOOK_SECRET:
        # Not ready by spec; treat as 503
        raise HTTPException(status_code=503, detail="WEBHOOK_SECRET not configured")

    if not x_sig:
        inc_webhook_result("invalid_signature")
        request.state.log_extra.update(
            {
                "result": "invalid_signature",
                "dup": False,
            }
        )
        raise HTTPException(status_code=401, detail="invalid signature")

    expected_sig = compute_signature(settings.WEBHOOK_SECRET, raw_body)
    if not hmac.compare_digest(expected_sig, x_sig.lower()):
        # some clients may send uppercase; compare as lower
        inc_webhook_result("invalid_signature")
        request.state.log_extra.update(
            {
                "result": "invalid_signature",
                "dup": False,
            }
        )
        raise HTTPException(status_code=401, detail="invalid signature")

    # Now parse JSON with Pydantic
    payload = WebhookPayload.model_validate_json(raw_body)

    created_at = iso_now()
    message, duplicate = insert_message(
        db,
        message_id=payload.message_id,
        from_msisdn=payload.from_,
        to_msisdn=payload.to,
        ts=payload.ts,
        text=payload.text,
        created_at=created_at,
    )

    result = "duplicate" if duplicate else "created"
    inc_webhook_result(result)

    # enrich logs
    request.state.log_extra.update(
        {
            "message_id": payload.message_id,
            "dup": duplicate,
            "result": result,
        }
    )

    return {"status": "ok"}


@app.get("/messages", response_model=MessagesResponse)
def get_messages(
    db: Session = Depends(get_db),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    from_: Optional[str] = Query(default=None, alias="from"),
    since: Optional[str] = Query(default=None),
    q: Optional[str] = Query(default=None),
):
    rows, total = list_messages(
        db,
        limit=limit,
        offset=offset,
        from_msisdn=from_,
        since_ts=since,
        q=q,
    )

    data = [
        MessagesResponseItem(
            message_id=m.message_id,
            from_=m.from_msisdn,
            to=m.to_msisdn,
            ts=m.ts,
            text=m.text,
        )
        for m in rows
    ]

    return MessagesResponse(
        data=data,
        total=total,
        limit=limit,
        offset=offset,
    )


@app.get("/stats")
def stats(db: Session = Depends(get_db)):
    return get_stats(db)


@app.get("/metrics")
def metrics():
    text = render_metrics()
    return PlainTextResponse(content=text, media_type="text/plain")
