"""Integration tests for ``RequestContextMiddleware`` (request id + request-summary log).

Uses the ``api_client`` fixture (real app, rolled-back ``db_session``) plus
``caplog`` to observe the one summary log line per request.
"""

from __future__ import annotations

import logging
import re
from collections.abc import Iterator
from typing import Any
from uuid import UUID, uuid4

import pytest
from app.api.middleware import REQUEST_ID_HEADER
from app.models.pet import Pet
from app.services.exceptions import PetServiceError
from fastapi.testclient import TestClient

REGISTER_URL = "/api/v1/auth/register"
LOGIN_URL = "/api/v1/auth/login"
PETS_URL = "/api/v1/pets"
PASSWORD = "s3cure-passphrase-value"

_SAFE_ID = re.compile(r"^[A-Za-z0-9-]{1,64}$")


def _register(client: TestClient, **overrides: object) -> dict[str, Any]:
    body: dict[str, object] = {
        "email": "george@example.com",
        "password": PASSWORD,
        "first_name": "George",
        "last_name": "Ovuworie",
    }
    body.update(overrides)
    response = client.post(REGISTER_URL, json=body)
    assert response.status_code == 201
    created: dict[str, Any] = response.json()
    return created


def _login(client: TestClient, email: str) -> str:
    response = client.post(LOGIN_URL, json={"email": email, "password": PASSWORD})
    assert response.status_code == 200
    token: str = response.json()["access_token"]
    return token


def _bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _auth(client: TestClient, **overrides: object) -> tuple[dict[str, Any], dict[str, str]]:
    user = _register(client, **overrides)
    return user, _bearer(_login(client, str(user["email"])))


def _summaries_for(records: list[logging.LogRecord], path: str) -> list[logging.LogRecord]:
    return [r for r in records if getattr(r, "path", None) == path]


# --------------------------------------------------------------------------- #
# Request-id: generation, echo, validation
# --------------------------------------------------------------------------- #


def test_generates_a_request_id_when_none_supplied(api_client: TestClient) -> None:
    response = api_client.get("/health")

    assert response.status_code == 200
    request_id = response.headers.get(REQUEST_ID_HEADER)
    assert request_id is not None
    assert _SAFE_ID.fullmatch(request_id)


def test_valid_client_supplied_request_id_is_echoed(api_client: TestClient) -> None:
    response = api_client.get("/health", headers={REQUEST_ID_HEADER: "trace-abc-123"})

    assert response.headers.get(REQUEST_ID_HEADER) == "trace-abc-123"


def test_overlong_request_id_is_replaced_not_rejected(api_client: TestClient) -> None:
    unsafe = "x" * 100  # exceeds the 64-character allow-list bound

    response = api_client.get("/health", headers={REQUEST_ID_HEADER: unsafe})

    assert response.status_code == 200
    request_id = response.headers.get(REQUEST_ID_HEADER)
    assert request_id is not None
    assert request_id != unsafe
    assert _SAFE_ID.fullmatch(request_id)


def test_request_id_with_disallowed_characters_is_replaced_not_rejected(
    api_client: TestClient,
) -> None:
    response = api_client.get("/health", headers={REQUEST_ID_HEADER: "has spaces!"})

    assert response.status_code == 200
    request_id = response.headers.get(REQUEST_ID_HEADER)
    assert request_id is not None
    assert request_id != "has spaces!"
    assert _SAFE_ID.fullmatch(request_id)


def test_request_id_header_present_on_error_responses(api_client: TestClient) -> None:
    response = api_client.get(PETS_URL)  # unauthenticated -> 401

    assert response.status_code == 401
    request_id = response.headers.get(REQUEST_ID_HEADER)
    assert request_id is not None
    assert _SAFE_ID.fullmatch(request_id)


# --------------------------------------------------------------------------- #
# Request-summary log content
# --------------------------------------------------------------------------- #


def test_request_summary_matches_the_response_header(
    api_client: TestClient, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.INFO)

    response = api_client.get("/health", headers={REQUEST_ID_HEADER: "match-me-123"})

    assert response.headers.get(REQUEST_ID_HEADER) == "match-me-123"
    summaries = _summaries_for(caplog.records, "/health")
    assert len(summaries) == 1
    assert summaries[0].request_id == "match-me-123"  # type: ignore[attr-defined]


def test_request_summary_contains_method_status_and_numeric_duration(
    api_client: TestClient, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.INFO)

    response = api_client.get("/health")

    assert response.status_code == 200
    summaries = _summaries_for(caplog.records, "/health")
    assert len(summaries) == 1
    record = summaries[0]
    assert record.method == "GET"  # type: ignore[attr-defined]
    assert record.status_code == 200  # type: ignore[attr-defined]
    assert isinstance(record.duration_ms, int | float)  # type: ignore[attr-defined]
    assert record.duration_ms >= 0  # type: ignore[attr-defined]
    assert record.levelno == logging.INFO
    assert not hasattr(record, "user_id")


def test_request_summary_includes_authenticated_user_id(
    api_client: TestClient, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.INFO)
    user, headers = _auth(api_client)

    response = api_client.get(PETS_URL, headers=headers)

    assert response.status_code == 200
    summaries = _summaries_for(caplog.records, PETS_URL)
    assert len(summaries) == 1
    assert summaries[0].user_id == user["id"]  # type: ignore[attr-defined]


def test_query_parameters_are_never_logged(
    api_client: TestClient, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.INFO)
    _user, headers = _auth(api_client)

    api_client.get(PETS_URL, headers=headers, params={"limit": 5, "offset": 0})

    summaries = _summaries_for(caplog.records, PETS_URL)
    assert len(summaries) == 1
    assert "?" not in summaries[0].path  # type: ignore[attr-defined]
    assert "limit" not in summaries[0].path  # type: ignore[attr-defined]


def test_expected_401_produces_no_error_level_log(
    api_client: TestClient, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.INFO)

    response = api_client.get(PETS_URL)

    assert response.status_code == 401
    assert not any(r.levelno >= logging.ERROR for r in caplog.records)
    summaries = _summaries_for(caplog.records, PETS_URL)
    assert len(summaries) == 1
    assert summaries[0].status_code == 401  # type: ignore[attr-defined]


def test_expected_404_produces_no_error_level_log(
    api_client: TestClient, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.INFO)
    _user, headers = _auth(api_client)

    response = api_client.get(f"{PETS_URL}/{uuid4()}", headers=headers)

    assert response.status_code == 404
    assert not any(r.levelno >= logging.ERROR for r in caplog.records)


# --------------------------------------------------------------------------- #
# Unexpected error: exactly one traceback, no duplication
# --------------------------------------------------------------------------- #


class _RaisingPetService:
    def __init__(self, exc: Exception) -> None:
        self._exc = exc

    def list_for_owner(self, owner_id: UUID, *, limit: int, offset: int) -> list[Pet]:
        raise self._exc


def _client_raising(exc: Exception) -> Iterator[TestClient]:
    from app.api.deps import get_current_user, get_pet_service
    from app.main import app
    from app.models.user import User

    fake_user = User(
        email="fake@example.com", password_hash="x", first_name="Fake", last_name="User"
    )
    app.dependency_overrides[get_current_user] = lambda: fake_user
    app.dependency_overrides[get_pet_service] = lambda: _RaisingPetService(exc)
    try:
        with TestClient(app, raise_server_exceptions=False) as client:
            yield client
    finally:
        app.dependency_overrides.pop(get_current_user, None)
        app.dependency_overrides.pop(get_pet_service, None)


@pytest.fixture
def pet_service_error_client() -> Iterator[TestClient]:
    yield from _client_raising(PetServiceError("internal detail that must not leak"))


def test_unexpected_error_produces_exactly_one_error_traceback(
    pet_service_error_client: TestClient, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.INFO)

    response = pet_service_error_client.get(PETS_URL)

    assert response.status_code == 500
    assert response.headers.get(REQUEST_ID_HEADER) is not None

    error_records = [r for r in caplog.records if r.levelno >= logging.ERROR]
    assert len(error_records) == 1
    assert error_records[0].exc_info is not None


def test_request_summary_does_not_duplicate_the_traceback(
    pet_service_error_client: TestClient, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.INFO)

    response = pet_service_error_client.get(PETS_URL)

    assert response.status_code == 500
    summaries = _summaries_for(caplog.records, PETS_URL)
    assert len(summaries) == 1
    assert summaries[0].status_code == 500  # type: ignore[attr-defined]
    assert summaries[0].levelno < logging.ERROR
    assert summaries[0].exc_info is None
