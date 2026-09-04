"""Unit tests for the Step 3J logging configuration.

No HTTP involved here -- see ``test_request_id_middleware.py`` for the
integration path and ``test_logging_security.py`` for the never-log guarantees.
"""

from __future__ import annotations

import json
import logging
import sys

import pytest
from app.core.config import Settings
from app.core.logging import (
    JsonFormatter,
    PlainFormatter,
    RequestIdFilter,
    bind_request_id,
    configure_logging,
    get_request_id,
    reset_request_id,
)


def _record(
    *, name: str = "app.test", level: int = logging.INFO, message: str = "hello", **extra: object
) -> logging.LogRecord:
    record = logging.makeLogRecord(
        {
            "name": name,
            "levelno": level,
            "levelname": logging.getLevelName(level),
            "msg": message,
            "created": 1_700_000_000.0,
        }
    )
    for key, value in extra.items():
        setattr(record, key, value)
    return record


def _record_with_exc_info() -> logging.LogRecord:
    try:
        raise ValueError("boom")
    except ValueError:
        record = _record()
        record.exc_info = sys.exc_info()
    return record


def _configure(monkeypatch: pytest.MonkeyPatch, *, environment: str, level: str = "INFO") -> None:
    monkeypatch.setenv("ENVIRONMENT", environment)
    monkeypatch.setenv("LOG_LEVEL", level)
    configure_logging(Settings())


# --------------------------------------------------------------------------- #
# configure_logging
# --------------------------------------------------------------------------- #


def test_configure_logging_sets_the_configured_level(monkeypatch: pytest.MonkeyPatch) -> None:
    _configure(monkeypatch, environment="local", level="DEBUG")

    assert logging.getLogger("app").getEffectiveLevel() == logging.DEBUG


def test_configure_logging_uses_plain_formatter_for_local(monkeypatch: pytest.MonkeyPatch) -> None:
    _configure(monkeypatch, environment="local")

    (handler,) = logging.getLogger("app").handlers
    assert isinstance(handler.formatter, PlainFormatter)


def test_configure_logging_uses_json_formatter_for_production(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _configure(monkeypatch, environment="production")

    (handler,) = logging.getLogger("app").handlers
    assert isinstance(handler.formatter, JsonFormatter)


def test_configure_logging_replaces_handlers_on_repeat_calls(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _configure(monkeypatch, environment="local")
    _configure(monkeypatch, environment="local")

    assert len(logging.getLogger("app").handlers) == 1


def test_configure_logging_does_not_touch_uvicorn_loggers(monkeypatch: pytest.MonkeyPatch) -> None:
    uvicorn_error = logging.getLogger("uvicorn.error")
    before_handlers = list(uvicorn_error.handlers)
    before_level = uvicorn_error.level

    _configure(monkeypatch, environment="production")

    assert logging.getLogger("uvicorn.error").handlers == before_handlers
    assert logging.getLogger("uvicorn.error").level == before_level


# --------------------------------------------------------------------------- #
# PlainFormatter
# --------------------------------------------------------------------------- #


def test_plain_formatter_includes_expected_fields() -> None:
    record = _record(message="hello world", request_id="req-123")

    line = PlainFormatter().format(record)

    assert "INFO" in line
    assert "app.test" in line
    assert "req-123" in line
    assert "hello world" in line
    with pytest.raises(json.JSONDecodeError):
        json.loads(line)


def test_plain_formatter_appends_allow_listed_extra_fields() -> None:
    record = _record(method="GET", path="/health", status_code=200, duration_ms=1.23)

    line = PlainFormatter().format(record)

    assert "method=GET" in line
    assert "path=/health" in line
    assert "status_code=200" in line
    assert "duration_ms=1.23" in line


def test_plain_formatter_appends_traceback_on_exc_info() -> None:
    record = _record_with_exc_info()

    line = PlainFormatter().format(record)

    assert "ValueError" in line
    assert "boom" in line


# --------------------------------------------------------------------------- #
# JsonFormatter
# --------------------------------------------------------------------------- #


def test_json_formatter_emits_valid_json_with_expected_keys() -> None:
    record = _record(message="hello", request_id="req-abc")

    payload = json.loads(JsonFormatter().format(record))

    assert set(payload) == {"timestamp", "level", "logger", "message", "request_id"}
    assert payload["level"] == "INFO"
    assert payload["logger"] == "app.test"
    assert payload["message"] == "hello"
    assert payload["request_id"] == "req-abc"


def test_json_formatter_includes_extra_fields_when_present() -> None:
    record = _record(method="GET", path="/api/v1/pets", status_code=200, duration_ms=4.5)

    payload = json.loads(JsonFormatter().format(record))

    assert payload["method"] == "GET"
    assert payload["path"] == "/api/v1/pets"
    assert payload["status_code"] == 200
    assert payload["duration_ms"] == 4.5


def test_json_formatter_never_includes_fields_outside_the_allow_list() -> None:
    record = _record(password="hunter2", email="george@example.com")

    text = JsonFormatter().format(record)
    payload = json.loads(text)

    assert "password" not in payload
    assert "email" not in payload
    assert "hunter2" not in text
    assert "george@example.com" not in text


def test_json_formatter_includes_traceback_for_exc_info() -> None:
    record = _record_with_exc_info()

    payload = json.loads(JsonFormatter().format(record))

    assert "traceback" in payload
    assert "ValueError" in payload["traceback"]
    assert "boom" in payload["traceback"]


# --------------------------------------------------------------------------- #
# Request-id filter and ContextVar
# --------------------------------------------------------------------------- #


def test_request_id_filter_defaults_to_placeholder_outside_a_request() -> None:
    record = _record()

    assert RequestIdFilter().filter(record) is True
    assert record.request_id == "-"  # type: ignore[attr-defined]


def test_request_id_filter_uses_the_bound_context_value() -> None:
    token = bind_request_id("bound-value")
    try:
        record = _record()
        RequestIdFilter().filter(record)
        assert record.request_id == "bound-value"  # type: ignore[attr-defined]
    finally:
        reset_request_id(token)


def test_bind_and_reset_request_id_restores_previous_value() -> None:
    assert get_request_id() == "-"

    token = bind_request_id("abc-123")
    assert get_request_id() == "abc-123"

    reset_request_id(token)
    assert get_request_id() == "-"


def test_nested_binds_do_not_leak() -> None:
    outer_token = bind_request_id("outer")
    inner_token = bind_request_id("inner")
    assert get_request_id() == "inner"

    reset_request_id(inner_token)
    assert get_request_id() == "outer"

    reset_request_id(outer_token)
    assert get_request_id() == "-"
