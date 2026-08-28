"""Structured logging + request correlation IDs (NFR-008).

configure_logging() replaces the root logger's handler with one that emits
one JSON object per line - every existing `logger.info(...)` /
`logger.exception(...)` call site in the codebase becomes structured and
correlated for free, without touching any of them, because the formatter
itself pulls the correlation ID from a contextvar rather than requiring
callers to pass one in.

CorrelationIdMiddleware sets that contextvar for the lifetime of a request.
It also covers DocumentService.process(), even though that runs as a
FastAPI BackgroundTask scheduled from the upload request: Starlette runs
background tasks by awaiting them in-place, in the same coroutine/context as
the request that scheduled them (the same reason create_upload's explicit
commit was needed - see document_service.py) - so the contextvar set here is
still active when a background task logs, with no extra propagation code.
"""
import contextvars
import json
import logging
import time
import uuid

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

_correlation_id: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "correlation_id", default=None
)

_REQUEST_ID_HEADER = "X-Request-ID"


def get_correlation_id() -> str | None:
    return _correlation_id.get()


class _JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, object] = {
            "timestamp": self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "correlation_id": get_correlation_id() or "-",
        }
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(payload)


def configure_logging(level: int = logging.INFO) -> None:
    handler = logging.StreamHandler()
    handler.setFormatter(_JsonFormatter())
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(level)


_request_logger = logging.getLogger("app.request")


class CorrelationIdMiddleware(BaseHTTPMiddleware):
    """Assigns/propagates a correlation ID (SRS Sec.9: 'all provider and
    infrastructure failures are logged with correlation IDs'; NFR-008: 'a
    correlation ID is present in logs across all layers'). Reuses an
    inbound X-Request-ID if the caller (e.g. a load balancer) already set
    one, so a single ID tracks a request across process boundaries too.
    """

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        correlation_id = request.headers.get(_REQUEST_ID_HEADER) or str(uuid.uuid4())
        token = _correlation_id.set(correlation_id)
        started = time.monotonic()
        try:
            _request_logger.info("%s %s started", request.method, request.url.path)
            response = await call_next(request)
        except Exception:
            _request_logger.exception("%s %s failed", request.method, request.url.path)
            raise
        else:
            duration_ms = round((time.monotonic() - started) * 1000, 1)
            _request_logger.info(
                "%s %s finished status=%s duration_ms=%s",
                request.method,
                request.url.path,
                response.status_code,
                duration_ms,
            )
            response.headers[_REQUEST_ID_HEADER] = correlation_id
            return response
        finally:
            _correlation_id.reset(token)
