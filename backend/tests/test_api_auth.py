"""Integration tests for the auth API (register + login).

Uses the ``api_client`` fixture: a ``TestClient`` whose ``get_db`` yields the
per-test transactional session, so every request is rolled back afterwards.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any
from uuid import UUID

import pytest
from app.core.jwt import decode_access_token
from app.models.user import User
from app.repositories.user import UserRepository
from app.schemas.auth import UserCreate
from app.services.exceptions import UserServiceError
from app.services.user import UserService
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

REGISTER_URL = "/api/v1/auth/register"
LOGIN_URL = "/api/v1/auth/login"
VALID_PASSWORD = "s3cure-passphrase-value"


def _payload(**overrides: object) -> dict[str, object]:
    body: dict[str, object] = {
        "email": "george@example.com",
        "password": VALID_PASSWORD,
        "first_name": "George",
        "last_name": "Ovuworie",
    }
    body.update(overrides)
    return body


def _register(client: TestClient, **overrides: object) -> dict[str, Any]:
    response = client.post(REGISTER_URL, json=_payload(**overrides))
    assert response.status_code == 201
    body: dict[str, Any] = response.json()
    return body


# --------------------------------------------------------------------------- #
# Registration
# --------------------------------------------------------------------------- #


def test_register_returns_201_and_public_user(api_client: TestClient) -> None:
    response = api_client.post(REGISTER_URL, json=_payload(phone="+45 11 22 33 44"))

    assert response.status_code == 201
    body = response.json()
    assert body["email"] == "george@example.com"
    assert body["first_name"] == "George"
    assert body["last_name"] == "Ovuworie"
    assert body["phone"] == "+45 11 22 33 44"
    assert body["is_active"] is True
    assert {"id", "created_at", "updated_at"} <= body.keys()
    assert "password" not in body
    assert "password_hash" not in body


def test_register_normalizes_email_in_response(api_client: TestClient) -> None:
    body = _register(api_client, email="  George@Example.COM  ")

    assert body["email"] == "george@example.com"


def test_register_persists_the_user(api_client: TestClient, db_session: Session) -> None:
    _register(api_client)

    assert UserRepository(db_session).get_by_email("george@example.com") is not None


def test_register_phone_is_optional(api_client: TestClient) -> None:
    body = _register(api_client)

    assert body["phone"] is None


def test_register_duplicate_email_returns_409_envelope(api_client: TestClient) -> None:
    _register(api_client)

    response = api_client.post(REGISTER_URL, json=_payload(first_name="Other", last_name="Name"))

    assert response.status_code == 409
    assert response.json() == {
        "error": {
            "code": "EMAIL_ALREADY_REGISTERED",
            "message": "Email already registered",
            "details": [],
        }
    }


def test_register_invalid_email_returns_422_envelope(api_client: TestClient) -> None:
    response = api_client.post(REGISTER_URL, json=_payload(email="not-an-email"))

    assert response.status_code == 422
    error = response.json()["error"]
    assert error["code"] == "VALIDATION_ERROR"
    assert error["message"] == "Request validation failed"
    assert ["body", "email"] in [d["location"] for d in error["details"]]


def test_register_short_password_returns_422(api_client: TestClient) -> None:
    response = api_client.post(REGISTER_URL, json=_payload(password="x" * 11))

    assert response.status_code == 422
    assert any(d["location"] == ["body", "password"] for d in response.json()["error"]["details"])


def test_register_long_password_returns_422(api_client: TestClient) -> None:
    response = api_client.post(REGISTER_URL, json=_payload(password="x" * 129))

    assert response.status_code == 422
    assert any(d["location"] == ["body", "password"] for d in response.json()["error"]["details"])


def test_register_missing_field_returns_422(api_client: TestClient) -> None:
    body = _payload()
    del body["last_name"]

    response = api_client.post(REGISTER_URL, json=body)

    assert response.status_code == 422
    details = response.json()["error"]["details"]
    assert any(d["location"] == ["body", "last_name"] and d["type"] == "missing" for d in details)


def test_register_unexpected_field_returns_422(api_client: TestClient) -> None:
    response = api_client.post(REGISTER_URL, json=_payload(is_active=True))

    assert response.status_code == 422
    assert any(d["location"] == ["body", "is_active"] for d in response.json()["error"]["details"])


def test_register_422_details_do_not_echo_submitted_password(api_client: TestClient) -> None:
    response = api_client.post(REGISTER_URL, json=_payload(first_name="", password="tinypw"))

    assert response.status_code == 422
    assert "tinypw" not in response.text


# --------------------------------------------------------------------------- #
# Login
# --------------------------------------------------------------------------- #


def test_login_returns_200_and_bearer_token(api_client: TestClient) -> None:
    _register(api_client)

    response = api_client.post(
        LOGIN_URL, json={"email": "george@example.com", "password": VALID_PASSWORD}
    )

    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer"
    assert isinstance(body["access_token"], str) and body["access_token"]


def test_login_token_subject_is_the_user_id(api_client: TestClient) -> None:
    created = _register(api_client)

    response = api_client.post(
        LOGIN_URL, json={"email": "george@example.com", "password": VALID_PASSWORD}
    )

    assert decode_access_token(response.json()["access_token"]).sub == created["id"]


def test_login_wrong_password_returns_401_envelope(api_client: TestClient) -> None:
    _register(api_client)

    response = api_client.post(
        LOGIN_URL, json={"email": "george@example.com", "password": "wrong-password"}
    )

    assert response.status_code == 401
    assert response.headers["WWW-Authenticate"] == "Bearer"
    assert response.json() == {
        "error": {
            "code": "INVALID_CREDENTIALS",
            "message": "Invalid email or password",
            "details": [],
        }
    }


def test_login_unknown_email_returns_401(api_client: TestClient) -> None:
    response = api_client.post(
        LOGIN_URL, json={"email": "nobody@example.com", "password": VALID_PASSWORD}
    )

    assert response.status_code == 401
    assert response.headers["WWW-Authenticate"] == "Bearer"


def test_login_inactive_user_returns_401(api_client: TestClient, db_session: Session) -> None:
    created = _register(api_client)
    UserService(db_session).deactivate(UUID(created["id"]))

    response = api_client.post(
        LOGIN_URL, json={"email": "george@example.com", "password": VALID_PASSWORD}
    )

    assert response.status_code == 401


def test_login_failure_responses_are_identical(api_client: TestClient, db_session: Session) -> None:
    _register(api_client, email="a@example.com")
    inactive = _register(api_client, email="c@example.com")
    UserService(db_session).deactivate(UUID(inactive["id"]))

    bodies: set[str] = set()
    for email, password in (
        ("unknown@example.com", VALID_PASSWORD),
        ("a@example.com", "wrong-password"),
        ("c@example.com", VALID_PASSWORD),
    ):
        response = api_client.post(LOGIN_URL, json={"email": email, "password": password})
        assert response.status_code == 401
        assert response.headers["WWW-Authenticate"] == "Bearer"
        bodies.add(response.text)

    assert len(bodies) == 1


def test_login_missing_password_returns_422_envelope(api_client: TestClient) -> None:
    response = api_client.post(LOGIN_URL, json={"email": "george@example.com"})

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


# --------------------------------------------------------------------------- #
# Error envelope for non-route / server errors
# --------------------------------------------------------------------------- #


def test_unknown_route_returns_404_envelope(api_client: TestClient) -> None:
    response = api_client.get("/api/v1/auth/does-not-exist")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "NOT_FOUND"
    assert response.json()["error"]["details"] == []


def test_wrong_method_returns_405_envelope(api_client: TestClient) -> None:
    response = api_client.get(LOGIN_URL)

    assert response.status_code == 405
    assert response.json()["error"]["code"] == "METHOD_NOT_ALLOWED"


def test_health_endpoint_is_unaffected(api_client: TestClient) -> None:
    response = api_client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}


class _RaisingService:
    def __init__(self, exc: Exception) -> None:
        self._exc = exc

    def register(self, payload: UserCreate) -> User:
        raise self._exc


def _client_raising(exc: Exception) -> Iterator[TestClient]:
    from app.api.deps import get_user_service
    from app.main import app

    app.dependency_overrides[get_user_service] = lambda: _RaisingService(exc)
    try:
        with TestClient(app, raise_server_exceptions=False) as client:
            yield client
    finally:
        app.dependency_overrides.pop(get_user_service, None)


@pytest.fixture
def service_error_client() -> Iterator[TestClient]:
    yield from _client_raising(UserServiceError("internal detail that must not leak"))


@pytest.fixture
def crashing_client() -> Iterator[TestClient]:
    yield from _client_raising(RuntimeError("internal detail that must not leak"))


def test_unmapped_service_error_returns_500_envelope(service_error_client: TestClient) -> None:
    response = service_error_client.post(REGISTER_URL, json=_payload())

    assert response.status_code == 500
    body = response.json()
    assert body["error"]["code"] == "INTERNAL_SERVER_ERROR"
    assert body["error"]["details"] == []
    assert "internal detail that must not leak" not in response.text


def test_unexpected_error_returns_500_envelope(crashing_client: TestClient) -> None:
    response = crashing_client.post(REGISTER_URL, json=_payload())

    assert response.status_code == 500
    assert response.json()["error"]["code"] == "INTERNAL_SERVER_ERROR"
    assert "internal detail that must not leak" not in response.text
    assert "Traceback" not in response.text
