"""Tests for the ``get_current_user`` FastAPI dependency.

The dependency has no production route yet (that arrives with ``/users/me``), so
each test mounts a throwaway probe route on a standalone ``FastAPI`` app and uses
the rolled-back ``db_session`` fixture, so nothing leaks between tests.
"""

from __future__ import annotations

import base64
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

import jwt
import pytest
from app.api.deps import CurrentUserDep
from app.api.errors import install_error_handlers
from app.core.config import settings
from app.core.jwt import ALGORITHM, create_access_token
from app.db.session import get_db
from app.models.user import User
from app.schemas.auth import UserCreate
from app.services.user import UserService
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

PASSWORD = "s3cure-passphrase-value"
PROBE_URL = "/_probe/me"

_UNAUTHORIZED_BODY: dict[str, Any] = {
    "error": {"code": "NOT_AUTHENTICATED", "message": "Not authenticated", "details": []}
}


@pytest.fixture
def current_user_client(db_session: Session) -> Iterator[TestClient]:
    """A ``TestClient`` for a throwaway app whose only route requires ``get_current_user``."""
    app = FastAPI()
    install_error_handlers(app)

    @app.get(PROBE_URL)
    def _probe(user: CurrentUserDep) -> dict[str, str]:
        return {"id": str(user.id), "email": user.email}

    app.dependency_overrides[get_db] = lambda: db_session
    with TestClient(app) as client:
        yield client


def _make_user(
    db_session: Session, *, email: str = "george@example.com", active: bool = True
) -> User:
    service = UserService(db_session)
    user = service.register(
        UserCreate(
            email=email,
            password=PASSWORD,
            first_name="George",
            last_name="Ovuworie",
        )
    )
    if not active:
        service.deactivate(user.id)
    return user


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _encode(claims: dict[str, Any]) -> str:
    return jwt.encode(claims, settings.JWT_SECRET_KEY, algorithm=ALGORITHM)


def _tamper_signature(token: str) -> str:
    header, payload, signature = token.split(".")
    raw = base64.urlsafe_b64decode(signature + "=" * (-len(signature) % 4))
    corrupted = bytes([raw[0] ^ 0xFF]) + raw[1:]
    corrupted_b64 = base64.urlsafe_b64encode(corrupted).rstrip(b"=").decode("ascii")
    return f"{header}.{payload}.{corrupted_b64}"


def _assert_unauthorized(response: Any) -> None:
    assert response.status_code == 401
    assert response.headers["WWW-Authenticate"] == "Bearer"
    assert response.json() == _UNAUTHORIZED_BODY


# --------------------------------------------------------------------------- #
# 1. Success
# --------------------------------------------------------------------------- #


def test_valid_active_user_returns_200(
    current_user_client: TestClient, db_session: Session
) -> None:
    user = _make_user(db_session)
    token = create_access_token(str(user.id))

    response = current_user_client.get(PROBE_URL, headers=_auth(token))

    assert response.status_code == 200
    assert response.json() == {"id": str(user.id), "email": "george@example.com"}


# --------------------------------------------------------------------------- #
# 2-11. Every rejection is the identical standardised 401
# --------------------------------------------------------------------------- #


def test_missing_authorization_header_is_401(current_user_client: TestClient) -> None:
    _assert_unauthorized(current_user_client.get(PROBE_URL))


def test_non_bearer_scheme_is_401(current_user_client: TestClient) -> None:
    basic = base64.b64encode(b"george:secret").decode("ascii")
    _assert_unauthorized(
        current_user_client.get(PROBE_URL, headers={"Authorization": f"Basic {basic}"})
    )


def test_malformed_or_empty_bearer_is_401(current_user_client: TestClient) -> None:
    _assert_unauthorized(current_user_client.get(PROBE_URL, headers={"Authorization": "Bearer"}))
    _assert_unauthorized(current_user_client.get(PROBE_URL, headers={"Authorization": "Bearer "}))
    _assert_unauthorized(
        current_user_client.get(PROBE_URL, headers={"Authorization": "not-a-real-scheme"})
    )


def test_tampered_signature_is_401(current_user_client: TestClient, db_session: Session) -> None:
    user = _make_user(db_session)
    tampered = _tamper_signature(create_access_token(str(user.id)))

    _assert_unauthorized(current_user_client.get(PROBE_URL, headers=_auth(tampered)))


def test_expired_token_is_401(current_user_client: TestClient, db_session: Session) -> None:
    user = _make_user(db_session)
    token = create_access_token(str(user.id), expires_delta=timedelta(minutes=-1))

    _assert_unauthorized(current_user_client.get(PROBE_URL, headers=_auth(token)))


def test_wrong_token_type_is_401(current_user_client: TestClient, db_session: Session) -> None:
    user = _make_user(db_session)
    now = datetime.now(UTC)
    token = _encode(
        {
            "sub": str(user.id),
            "type": "refresh",
            "iat": now,
            "exp": now + timedelta(minutes=5),
        }
    )

    _assert_unauthorized(current_user_client.get(PROBE_URL, headers=_auth(token)))


def test_missing_sub_claim_is_401(current_user_client: TestClient) -> None:
    now = datetime.now(UTC)
    token = _encode({"type": "access", "iat": now, "exp": now + timedelta(minutes=5)})

    _assert_unauthorized(current_user_client.get(PROBE_URL, headers=_auth(token)))


def test_non_uuid_sub_is_401(current_user_client: TestClient) -> None:
    token = create_access_token("not-a-uuid")

    _assert_unauthorized(current_user_client.get(PROBE_URL, headers=_auth(token)))


def test_nonexistent_user_is_401(current_user_client: TestClient) -> None:
    token = create_access_token(str(uuid4()))

    _assert_unauthorized(current_user_client.get(PROBE_URL, headers=_auth(token)))


def test_inactive_user_is_401(current_user_client: TestClient, db_session: Session) -> None:
    user = _make_user(db_session, active=False)
    token = create_access_token(str(user.id))

    _assert_unauthorized(current_user_client.get(PROBE_URL, headers=_auth(token)))


# --------------------------------------------------------------------------- #
# 12. Fundamentally different failures -> byte-for-byte identical response
# --------------------------------------------------------------------------- #


def test_distinct_failures_produce_identical_response(
    current_user_client: TestClient, db_session: Session
) -> None:
    inactive = _make_user(db_session, email="inactive@example.com", active=False)

    responses = [
        current_user_client.get(PROBE_URL),  # no header
        current_user_client.get(PROBE_URL, headers={"Authorization": "Basic Zm9vOmJhcg=="}),
        current_user_client.get(PROBE_URL, headers=_auth("garbage.jwt.value")),  # undecodable
        current_user_client.get(PROBE_URL, headers=_auth(create_access_token("not-a-uuid"))),
        current_user_client.get(PROBE_URL, headers=_auth(create_access_token(str(uuid4())))),
        current_user_client.get(PROBE_URL, headers=_auth(create_access_token(str(inactive.id)))),
    ]

    assert {r.status_code for r in responses} == {401}
    assert {r.headers.get("WWW-Authenticate") for r in responses} == {"Bearer"}

    bodies = {r.content for r in responses}
    assert len(bodies) == 1  # every failure returns the exact same bytes
    assert responses[0].json() == _UNAUTHORIZED_BODY


# --------------------------------------------------------------------------- #
# 13. No token / JWT internals / traceback / DB details leak into the response
# --------------------------------------------------------------------------- #


def test_rejection_body_has_no_sensitive_leakage(
    current_user_client: TestClient, db_session: Session
) -> None:
    user = _make_user(db_session)
    valid = create_access_token(str(user.id))
    header, payload, _ = valid.split(".")
    tampered = _tamper_signature(valid)

    response = current_user_client.get(PROBE_URL, headers=_auth(tampered))
    text = response.text

    assert response.status_code == 401
    assert response.json() == _UNAUTHORIZED_BODY
    for leaked in (
        tampered,
        valid,
        header,
        payload,
        str(user.id),
        "Traceback",
        "Signature",
        "PyJWT",
        "could not validate access token",
        "psycopg",
        "sqlalchemy",
        "postgresql",
        "SELECT",
    ):
        assert leaked not in text
