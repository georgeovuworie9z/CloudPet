"""Unit tests for HS256 access-token issue/verify (no database)."""

from __future__ import annotations

import base64
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
    # Corrupt the signature at the byte level so the change is guaranteed:
    # flipping a single base64url character can be a no-op, because the final
    # character of a 32-byte HMAC signature carries 2 unused bits.
    header, payload, signature = create_access_token("user-abc-123").split(".")
    signature_bytes = base64.urlsafe_b64decode(signature + "=" * (-len(signature) % 4))
    corrupted = bytes([signature_bytes[0] ^ 0xFF]) + signature_bytes[1:]
    tampered_signature = base64.urlsafe_b64encode(corrupted).rstrip(b"=").decode("ascii")
    tampered = f"{header}.{payload}.{tampered_signature}"

    assert tampered_signature != signature
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
