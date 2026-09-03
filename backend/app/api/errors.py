"""Standardised API error envelope and the handlers that produce it.

Every non-2xx response has the shape::

    {"error": {"code": "STRING_CODE", "message": "...", "details": []}}

``details`` is populated only for request-validation (422) failures.
"""

from __future__ import annotations

import logging
from http import HTTPStatus
from typing import Any, cast

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.services.exceptions import (
    DuplicateEmailError,
    InvalidCredentialsError,
    InvalidProfileUpdateError,
    UserServiceError,
)

logger = logging.getLogger("app.api")

_INTERNAL_ERROR_MESSAGE = "An internal error occurred"


class NotAuthenticatedError(Exception):
    """Raised by ``get_current_user`` when a request is not authenticated.

    Covers a missing/non-Bearer header, an invalid/expired/wrong-type token, a
    non-UUID subject, and a missing or inactive user -- all indistinguishable in
    the response.
    """


class ErrorDetail(BaseModel):
    """One field-level problem, used for validation errors."""

    location: list[str | int]
    message: str
    type: str


class ErrorBody(BaseModel):
    code: str
    message: str
    details: list[ErrorDetail] = Field(default_factory=list)


class ErrorResponse(BaseModel):
    """The body of every non-2xx API response."""

    error: ErrorBody


def _reason_phrase(status_code: int) -> str:
    """Return the standard reason phrase for ``status_code``, or a safe fallback.

    ``HTTPStatus(code)`` raises ``ValueError`` for unknown/non-standard codes;
    this must never turn into a secondary error inside an error handler.
    """
    try:
        return HTTPStatus(status_code).phrase
    except ValueError:
        return "Error"


def _envelope(
    *,
    status_code: int,
    code: str,
    message: str,
    details: list[ErrorDetail] | None = None,
    headers: dict[str, str] | None = None,
) -> JSONResponse:
    body = ErrorResponse(error=ErrorBody(code=code, message=message, details=details or []))
    return JSONResponse(status_code=status_code, content=body.model_dump(), headers=headers)


def _handle_validation_error(request: Request, exc: Exception) -> JSONResponse:
    validation_exc = cast(RequestValidationError, exc)
    details = [
        ErrorDetail(
            location=list(error["loc"]),
            message=str(error["msg"]),
            type=str(error["type"]),
        )
        for error in validation_exc.errors()
    ]
    return _envelope(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        code="VALIDATION_ERROR",
        message="Request validation failed",
        details=details,
    )


def _handle_duplicate_email(request: Request, exc: Exception) -> JSONResponse:
    return _envelope(
        status_code=status.HTTP_409_CONFLICT,
        code="EMAIL_ALREADY_REGISTERED",
        message="Email already registered",
    )


def _handle_invalid_credentials(request: Request, exc: Exception) -> JSONResponse:
    return _envelope(
        status_code=status.HTTP_401_UNAUTHORIZED,
        code="INVALID_CREDENTIALS",
        message="Invalid email or password",
        headers={"WWW-Authenticate": "Bearer"},
    )


def _handle_not_authenticated(request: Request, exc: Exception) -> JSONResponse:
    return _envelope(
        status_code=status.HTTP_401_UNAUTHORIZED,
        code="NOT_AUTHENTICATED",
        message="Not authenticated",
        headers={"WWW-Authenticate": "Bearer"},
    )


def _handle_invalid_profile_update(request: Request, exc: Exception) -> JSONResponse:
    return _envelope(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        code="INVALID_PROFILE_UPDATE",
        message=str(exc),
    )


def _handle_unmapped_service_error(request: Request, exc: Exception) -> JSONResponse:
    logger.exception("Unhandled service error")
    return _envelope(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        code="INTERNAL_SERVER_ERROR",
        message=_INTERNAL_ERROR_MESSAGE,
    )


def _handle_http_exception(request: Request, exc: Exception) -> JSONResponse:
    http_exc = cast(StarletteHTTPException, exc)
    message = (
        http_exc.detail
        if isinstance(http_exc.detail, str)
        else _reason_phrase(http_exc.status_code)
    )
    code = {404: "NOT_FOUND", 405: "METHOD_NOT_ALLOWED"}.get(http_exc.status_code, "HTTP_ERROR")
    headers: dict[str, str] | None = dict(http_exc.headers) if http_exc.headers else None
    return _envelope(status_code=http_exc.status_code, code=code, message=message, headers=headers)


def _handle_unexpected_error(request: Request, exc: Exception) -> JSONResponse:
    logger.exception("Unhandled exception")
    return _envelope(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        code="INTERNAL_SERVER_ERROR",
        message=_INTERNAL_ERROR_MESSAGE,
    )


def install_error_handlers(app: FastAPI) -> None:
    """Register the standardised error handlers on ``app``."""
    handlers: list[tuple[type[Exception], Any]] = [
        (RequestValidationError, _handle_validation_error),
        (DuplicateEmailError, _handle_duplicate_email),
        (InvalidCredentialsError, _handle_invalid_credentials),
        (NotAuthenticatedError, _handle_not_authenticated),
        (InvalidProfileUpdateError, _handle_invalid_profile_update),
        (UserServiceError, _handle_unmapped_service_error),
        (StarletteHTTPException, _handle_http_exception),
        (Exception, _handle_unexpected_error),
    ]
    for exc_type, handler in handlers:
        app.add_exception_handler(exc_type, handler)
