"""Centralized application logging configuration.

Configures the ``app`` logger namespace only -- never the root logger and
never any ``uvicorn`` / ``uvicorn.access`` / ``uvicorn.error`` logger. Uvicorn
manages its own logging independently, so its console/access logging (and
Docker's stdout/stderr capture of it) is unaffected. CloudPet's own loggers
(``app.api``, ``app.storage``, ``app.services.user``, ...) are children of the
``app`` namespace and pick up this configuration purely through normal
logger-hierarchy propagation -- nothing here is wired directly to them.

Records still propagate from ``app`` up to the root logger (the default), so
tooling that attaches at root -- notably pytest's ``caplog`` -- observes them
without any extra setup; root itself is never given a handler, so nothing is
emitted twice.

Formatters serialize an explicit, fixed field set only. They never serialize
``LogRecord.__dict__`` wholesale, so a stray attribute added by future code can
never silently leak into a log line.
"""

from __future__ import annotations

import json
import logging
from contextvars import ContextVar, Token
from datetime import UTC, datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.core.config import Settings

_NO_REQUEST_ID = "-"
_request_id_ctx: ContextVar[str | None] = ContextVar("cloudpet_request_id", default=None)

# The only "extra" fields any formatter will ever emit, regardless of which log
# call supplied them. Anything else set on a LogRecord is never serialized.
_EXTRA_FIELDS: tuple[str, ...] = ("method", "path", "status_code", "duration_ms", "user_id")


def bind_request_id(value: str) -> Token[str | None]:
    """Bind ``value`` as the current request's correlation id; returns a reset token."""
    return _request_id_ctx.set(value)


def reset_request_id(token: Token[str | None]) -> None:
    """Undo a prior :func:`bind_request_id` call. Always call this in a ``finally``."""
    _request_id_ctx.reset(token)


def get_request_id() -> str:
    """The current request's correlation id, or a placeholder outside a request."""
    return _request_id_ctx.get() or _NO_REQUEST_ID


class RequestIdFilter(logging.Filter):
    """Stamps every log record with the current request's correlation id."""

    def filter(self, record: logging.LogRecord) -> bool:
        setattr(record, "request_id", get_request_id())  # noqa: B010
        return True


def _extra_fields(record: logging.LogRecord) -> dict[str, object]:
    return {name: getattr(record, name) for name in _EXTRA_FIELDS if hasattr(record, name)}


class PlainFormatter(logging.Formatter):
    """Human-readable formatter for local/test environments.

    Always emits: timestamp, level, logger name, request id, message. Any
    allow-listed extra field present on the record (e.g. a request summary's
    ``method`` / ``path`` / ``status_code`` / ``duration_ms`` / ``user_id``) is
    appended as a ``key=value`` pair. A traceback is appended when the record
    carries exception info.
    """

    def format(self, record: logging.LogRecord) -> str:
        timestamp = datetime.fromtimestamp(record.created, tz=UTC).isoformat()
        request_id = getattr(record, "request_id", _NO_REQUEST_ID)
        line = (
            f"{timestamp} {record.levelname:<8} {record.name} [{request_id}] {record.getMessage()}"
        )
        extra = _extra_fields(record)
        if extra:
            line += " " + " ".join(f"{key}={value}" for key, value in extra.items())
        if record.exc_info:
            line += "\n" + self.formatException(record.exc_info)
        return line


class JsonFormatter(logging.Formatter):
    """Structured JSON formatter for staging/production.

    Always emits: timestamp, level, logger, message, request_id. Adds a
    ``traceback`` key only when the record carries exception info, plus any
    allow-listed extra field present on the record. Never serializes
    ``LogRecord.__dict__`` or any field outside this fixed set.
    """

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, object] = {
            "timestamp": datetime.fromtimestamp(record.created, tz=UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "request_id": getattr(record, "request_id", _NO_REQUEST_ID),
        }
        payload.update(_extra_fields(record))
        if record.exc_info:
            payload["traceback"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


def configure_logging(settings: Settings) -> None:
    """Configure the ``app`` logger namespace only.

    Deliberately does not touch the root logger's handlers, nor any
    ``uvicorn*`` logger -- Uvicorn keeps configuring and using those exactly as
    it already does. Safe to call more than once: it always replaces the
    ``app`` logger's handler list rather than appending to it, so repeated
    calls (e.g. module reload) never accumulate duplicate handlers.
    """
    app_logger = logging.getLogger("app")
    app_logger.setLevel(settings.LOG_LEVEL)

    formatter: logging.Formatter
    if settings.ENVIRONMENT in ("staging", "production"):
        formatter = JsonFormatter()
    else:
        formatter = PlainFormatter()

    handler = logging.StreamHandler()
    handler.setFormatter(formatter)
    handler.addFilter(RequestIdFilter())

    app_logger.handlers = [handler]

    # A prior logging.config.fileConfig() / dictConfig() call elsewhere in this
    # process -- notably Alembic's alembic/env.py, invoked by the test harness
    # before this function ever runs -- disables every logger that already
    # existed at that point unless it is explicitly named in that config. Undo
    # that for our own namespace only, so a migration run earlier in the
    # process can never silence CloudPet's application logs. This never
    # touches "uvicorn" / "uvicorn.access" / "uvicorn.error" or any other
    # logger outside "app"/"app.*".
    for name, logger in logging.Logger.manager.loggerDict.items():
        if isinstance(logger, logging.Logger) and (name == "app" or name.startswith("app.")):
            logger.disabled = False
