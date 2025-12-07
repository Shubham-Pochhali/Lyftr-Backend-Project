import json
import logging
import time
import uuid
from datetime import datetime, timezone
from typing import Callable

from fastapi import Request, Response

from .config import settings
from .metrics import inc_http_request, observe_latency_ms


logger = logging.getLogger("app")
logger.setLevel(settings.LOG_LEVEL)
handler = logging.StreamHandler()
handler.setLevel(settings.LOG_LEVEL)
logger.addHandler(handler)


def iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


async def logging_middleware(request: Request, call_next: Callable) -> Response:
    request_id = str(uuid.uuid4())
    start = time.perf_counter()

    # store request_id in state so handlers can use it if needed
    request.state.request_id = request_id
    request.state.log_extra = {}

    response: Response
    try:
        response = await call_next(request)
    except Exception:
        latency_ms = (time.perf_counter() - start) * 1000.0
        log = {
            "ts": iso_now(),
            "level": "error",
            "request_id": request_id,
            "method": request.method,
            "path": request.url.path,
            "status": 500,
            "latency_ms": round(latency_ms, 2),
        }
        logger.error(json.dumps(log))
        raise

    latency_ms = (time.perf_counter() - start) * 1000.0
    status_code = response.status_code

    # metrics
    inc_http_request(request.url.path, status_code)
    observe_latency_ms(latency_ms)

    log = {
        "ts": iso_now(),
        "level": "info",
        "request_id": request_id,
        "method": request.method,
        "path": request.url.path,
        "status": status_code,
        "latency_ms": round(latency_ms, 2),
    }

    # add extra fields from handlers (e.g. webhook result)
    if isinstance(getattr(request.state, "log_extra", None), dict):
        log.update(request.state.log_extra)

    logger.info(json.dumps(log))
    return response
