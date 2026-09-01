"""Application-managed JWT access tokens.

Issues and verifies short-lived HS256 access tokens signed with
``settings.JWT_SECRET_KEY``. Refresh tokens are intentionally not implemented.

The ``sub`` claim carries the user id as a plain string. Converting it to a
``UUID`` and loading the corresponding user is the API layer's responsibility.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import jwt
from pydantic import BaseModel, ValidationError

from app.core.config import settings

ALGORITHM = "HS256"
ACCESS_TOKEN_TYPE = "access"

_GENERIC_ERROR = "could not validate access token"


class InvalidTokenError(Exception):
    """Raised when an access token is missing, malformed, expired, or otherwise invalid.

    The message is deliberately generic so it can be surfaced to clients without
    leaking why validation failed.
    """


class TokenPayload(BaseModel):
    """Decoded and validated claims of an access token."""

    sub: str
    type: str
    iat: datetime
    exp: datetime


def create_access_token(subject: str, expires_delta: timedelta | None = None) -> str:
    """Return a signed HS256 access token for ``subject``.

    ``subject`` is stored verbatim in the ``sub`` claim. ``expires_delta``
    defaults to ``settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES``.
    """
    now = datetime.now(UTC)
    if expires_delta is None:
        expires_delta = timedelta(minutes=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES)
    claims = {
        "sub": subject,
        "type": ACCESS_TOKEN_TYPE,
        "iat": now,
        "exp": now + expires_delta,
    }
    return jwt.encode(claims, settings.JWT_SECRET_KEY, algorithm=ALGORITHM)


def decode_access_token(token: str) -> TokenPayload:
    """Verify ``token`` and return its claims.

    Raises :class:`InvalidTokenError` for any bad signature, expired token,
    missing required claim, or wrong token type.
    """
    try:
        raw = jwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=[ALGORITHM],
            options={"require": ["exp", "iat", "sub"]},
        )
    except jwt.PyJWTError as exc:
        raise InvalidTokenError(_GENERIC_ERROR) from exc

    try:
        payload = TokenPayload.model_validate(raw)
    except ValidationError as exc:
        raise InvalidTokenError(_GENERIC_ERROR) from exc

    if payload.type != ACCESS_TOKEN_TYPE:
        raise InvalidTokenError(_GENERIC_ERROR)
    return payload
