"""Request-context middleware: correlation id, and one request-summary log per request.

This is the sole place that logs a per-request summary line -- routes,
services, and repositories do not log at this granularity, so a request is
never described more than once here. Unexpected-exception tracebacks remain
the sole responsibility of the handlers in :mod:`app.api.errors`; this
middleware never logs with ``exc_info`` and never duplicates that traceback.
"""

from __future__ import annotations

import logging
import re
import time
import uuid
from collections.abc import Awaitable, Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.core.logging import bind_request_id, reset_request_id

logger = logging.getLogger("app.api.middleware")

REQUEST_ID_HEADER = "X-Request-ID"

# Matches a UUIDv4 as well as any reasonable short trace-id convention; rejects
# whitespace, control characters, and punctuation that could break a log line.
_SAFE_REQUEST_ID = re.compile(r"^[A-Za-z0-9-]{1,64}$")


def _resolve_request_id(raw: str | None) -> str:
    """Return ``raw`` if it is a safe client-supplied id, else a fresh UUIDv4.

    The request id is diagnostics-only: it carries no authority and must never
    be used for authorization, idempotency, deduplication, or replay
    protection anywhere in the codebase. A malformed client-supplied value
    never fails the request -- it is silently replaced.
    """
    if raw is not None and _SAFE_REQUEST_ID.fullmatch(raw):
        return raw
    return str(uuid.uuid4())


class RequestContextMiddleware(BaseHTTPMiddleware):
    """Binds a correlation id to every request and logs one summary line for it."""

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        request_id = _resolve_request_id(request.headers.get(REQUEST_ID_HEADER))
        token = bind_request_id(request_id)
        started_at = time.perf_counter()
        try:
            try:
                response = await call_next(request)
            except Exception:
                # Only reachable if something bypasses app.api.errors' catch-all
                # Exception handler entirely (e.g. a bug inside the handler
                # itself). Log the outcome once, then let it propagate --
                # Starlette's own error middleware still produces a response.
                duration_ms = (time.perf_counter() - started_at) * 1000
                self._log_summary(request, status_code=500, duration_ms=duration_ms)
                raise
            duration_ms = (time.perf_counter() - started_at) * 1000
            self._log_summary(request, status_code=response.status_code, duration_ms=duration_ms)
            response.headers[REQUEST_ID_HEADER] = request_id
            return response
        finally:
            reset_request_id(token)

    @staticmethod
    def _log_summary(request: Request, *, status_code: int, duration_ms: float) -> None:
        extra: dict[str, object] = {
            "method": request.method,
            "path": request.url.path,
            "status_code": status_code,
            "duration_ms": round(duration_ms, 2),
        }
        user_id = getattr(request.state, "user_id", None)
        if user_id is not None:
            extra["user_id"] = str(user_id)

        level = logging.INFO if status_code < 400 else logging.WARNING
        logger.log(level, "request completed", extra=extra)
