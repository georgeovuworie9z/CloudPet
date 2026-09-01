"""Unit tests for HS256 access-token issue/verify (no database)."""

from __future__ import annotations

from datetime import timedelta

import jwt
import pytest
from app.core.config import settings
from app.core.jwt import (
    ALGORITHM,
    InvalidTokenError,
    TokenPayload,
    create_access_token,
    decode_access_token,
)


def test_round_trip_preserves_subject_and_type() -> None:
    payload = decode_access_token(create_access_token("user-abc-123"))

    assert isinstance(payload, TokenPayload)
    assert payload.sub == "user-abc-123"
    assert payload.type == "access"


def test_issued_before_expiry() -> None:
    payload = decode_access_token(create_access_token("user-abc-123"))

    assert payload.iat < payload.exp


def test_custom_expiry_is_honoured() -> None:
    payload = decode_access_token(
        create_access_token("user-abc-123", expires_delta=timedelta(minutes=5))
    )

    assert (payload.exp - payload.iat) == timedelta(minutes=5)


def test_expired_token_is_rejected() -> None:
    token = create_access_token("user-abc-123", expires_delta=timedelta(minutes=-1))

    with pytest.raises(InvalidTokenError):
        decode_access_token(token)


def test_tampered_token_is_rejected() -> None:
    token = create_access_token("user-abc-123")
    tampered = token[:-1] + ("a" if token[-1] != "a" else "b")

    with pytest.raises(InvalidTokenError):
        decode_access_token(tampered)


def test_token_signed_with_wrong_secret_is_rejected() -> None:
    forged = jwt.encode(
        {"sub": "user-abc-123", "type": "access"},
        "not-the-real-secret",
        algorithm=ALGORITHM,
    )

    with pytest.raises(InvalidTokenError):
        decode_access_token(forged)


def test_token_with_unexpected_algorithm_is_rejected() -> None:
    forged = jwt.encode(
        {"sub": "user-abc-123", "type": "access"},
        settings.JWT_SECRET_KEY,
        algorithm="HS512",
    )

    with pytest.raises(InvalidTokenError):
        decode_access_token(forged)


def test_token_missing_required_claims_is_rejected() -> None:
    forged = jwt.encode(
        {"sub": "user-abc-123", "type": "access"},
        settings.JWT_SECRET_KEY,
        algorithm=ALGORITHM,
    )

    with pytest.raises(InvalidTokenError):
        decode_access_token(forged)


def test_non_access_token_type_is_rejected() -> None:
    claims = jwt.decode(
        create_access_token("user-abc-123"),
        settings.JWT_SECRET_KEY,
        algorithms=[ALGORITHM],
    )
    claims["type"] = "refresh"
    refreshy = jwt.encode(claims, settings.JWT_SECRET_KEY, algorithm=ALGORITHM)

    with pytest.raises(InvalidTokenError):
        decode_access_token(refreshy)
