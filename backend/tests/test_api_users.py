"""Integration tests for the current-user endpoints.

``GET/PUT/DELETE /api/v1/users/me`` and ``GET /api/v1/auth/me``. Uses the
``api_client`` fixture (``get_db`` overridden to the rolled-back ``db_session``).
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from app.repositories.user import UserRepository
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

REGISTER_URL = "/api/v1/auth/register"
LOGIN_URL = "/api/v1/auth/login"
USERS_ME_URL = "/api/v1/users/me"
AUTH_ME_URL = "/api/v1/auth/me"
PASSWORD = "s3cure-passphrase-value"

_UNAUTHORIZED_BODY: dict[str, Any] = {
    "error": {"code": "NOT_AUTHENTICATED", "message": "Not authenticated", "details": []}
}


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


# --------------------------------------------------------------------------- #
# GET /users/me
# --------------------------------------------------------------------------- #


def test_get_users_me_returns_profile(api_client: TestClient) -> None:
    user, headers = _auth(api_client)

    response = api_client.get(USERS_ME_URL, headers=headers)

    assert response.status_code == 200
    assert response.json() == user
    assert "password" not in response.json()
    assert "password_hash" not in response.json()


def test_get_users_me_without_token_is_401(api_client: TestClient) -> None:
    response = api_client.get(USERS_ME_URL)

    assert response.status_code == 401
    assert response.headers["WWW-Authenticate"] == "Bearer"
    assert response.json() == _UNAUTHORIZED_BODY


def test_get_users_me_with_invalid_token_is_401(api_client: TestClient) -> None:
    response = api_client.get(USERS_ME_URL, headers=_bearer("not.a.valid.jwt"))

    assert response.status_code == 401
    assert response.json() == _UNAUTHORIZED_BODY


# --------------------------------------------------------------------------- #
# GET /auth/me
# --------------------------------------------------------------------------- #


def test_get_auth_me_matches_users_me(api_client: TestClient) -> None:
    user, headers = _auth(api_client)

    auth_me = api_client.get(AUTH_ME_URL, headers=headers)
    users_me = api_client.get(USERS_ME_URL, headers=headers)

    assert auth_me.status_code == 200
    assert auth_me.json() == user
    assert auth_me.json() == users_me.json()


def test_get_auth_me_without_token_is_401(api_client: TestClient) -> None:
    response = api_client.get(AUTH_ME_URL)

    assert response.status_code == 401
    assert response.json() == _UNAUTHORIZED_BODY


# --------------------------------------------------------------------------- #
# PUT /users/me
# --------------------------------------------------------------------------- #


def test_put_users_me_updates_supplied_field(api_client: TestClient, db_session: Session) -> None:
    user, headers = _auth(api_client, phone="+45 11 22 33 44")

    response = api_client.put(USERS_ME_URL, headers=headers, json={"first_name": "Georgina"})

    assert response.status_code == 200
    body = response.json()
    assert body["first_name"] == "Georgina"
    assert body["last_name"] == user["last_name"]
    assert body["phone"] == "+45 11 22 33 44"
    assert body["email"] == user["email"]
    assert body["id"] == user["id"]
    assert body["created_at"] == user["created_at"]
    assert body["is_active"] is True
    # NOTE: updated_at is not asserted -- see the test-harness note in the plan.

    db_session.expire_all()
    reloaded = UserRepository(db_session).get_by_id(UUID(str(user["id"])))
    assert reloaded is not None
    assert reloaded.first_name == "Georgina"


def test_put_users_me_null_phone_clears_it(api_client: TestClient) -> None:
    user, headers = _auth(api_client, phone="+45 11 22 33 44")
    assert user["phone"] == "+45 11 22 33 44"

    response = api_client.put(USERS_ME_URL, headers=headers, json={"phone": None})

    assert response.status_code == 200
    assert response.json()["phone"] is None


def test_put_users_me_empty_body_is_noop(api_client: TestClient) -> None:
    user, headers = _auth(api_client, phone="+45 11 22 33 44")

    response = api_client.put(USERS_ME_URL, headers=headers, json={})

    assert response.status_code == 200
    # Byte-identical: profile fields, id, created_at, updated_at and is_active
    # are all unchanged because no database write occurs.
    assert response.json() == user


def test_put_users_me_null_first_name_is_422_invalid_profile_update(api_client: TestClient) -> None:
    _user, headers = _auth(api_client)

    response = api_client.put(USERS_ME_URL, headers=headers, json={"first_name": None})

    assert response.status_code == 422
    error = response.json()["error"]
    assert error["code"] == "INVALID_PROFILE_UPDATE"
    assert error["details"] == []
    assert "first_name" in error["message"]


def test_put_users_me_null_last_name_is_422_invalid_profile_update(api_client: TestClient) -> None:
    _user, headers = _auth(api_client)

    response = api_client.put(USERS_ME_URL, headers=headers, json={"last_name": None})

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "INVALID_PROFILE_UPDATE"


def test_put_users_me_forbidden_field_is_422_validation_error(api_client: TestClient) -> None:
    user, headers = _auth(api_client)

    for forbidden in ({"email": "new@example.com"}, {"is_active": False}, {"id": user["id"]}):
        response = api_client.put(USERS_ME_URL, headers=headers, json=forbidden)
        assert response.status_code == 422
        assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_put_users_me_invalid_type_is_422_validation_error(api_client: TestClient) -> None:
    _user, headers = _auth(api_client)

    response = api_client.put(USERS_ME_URL, headers=headers, json={"first_name": 123})

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_put_users_me_does_not_change_email(api_client: TestClient) -> None:
    user, headers = _auth(api_client)

    response = api_client.put(USERS_ME_URL, headers=headers, json={"first_name": "Georgina"})

    assert response.json()["email"] == user["email"]


def test_put_users_me_without_token_is_401(api_client: TestClient) -> None:
    response = api_client.put(USERS_ME_URL, json={"first_name": "Georgina"})

    assert response.status_code == 401
    assert response.json() == _UNAUTHORIZED_BODY


# --------------------------------------------------------------------------- #
# DELETE /users/me
# --------------------------------------------------------------------------- #


def test_delete_users_me_returns_204_empty_body(api_client: TestClient) -> None:
    _user, headers = _auth(api_client)

    response = api_client.delete(USERS_ME_URL, headers=headers)

    assert response.status_code == 204
    assert response.content == b""


def test_delete_users_me_soft_deletes_the_row(api_client: TestClient, db_session: Session) -> None:
    user, headers = _auth(api_client)

    api_client.delete(USERS_ME_URL, headers=headers)

    db_session.expire_all()
    reloaded = UserRepository(db_session).get_by_id(UUID(str(user["id"])))
    assert reloaded is not None
    assert reloaded.is_active is False


def test_delete_users_me_then_same_token_is_401(api_client: TestClient) -> None:
    _user, headers = _auth(api_client)

    assert api_client.delete(USERS_ME_URL, headers=headers).status_code == 204

    response = api_client.get(USERS_ME_URL, headers=headers)
    assert response.status_code == 401
    assert response.json() == _UNAUTHORIZED_BODY


def test_delete_users_me_then_login_is_401_invalid_credentials(api_client: TestClient) -> None:
    user, headers = _auth(api_client)

    api_client.delete(USERS_ME_URL, headers=headers)

    response = api_client.post(LOGIN_URL, json={"email": user["email"], "password": PASSWORD})
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "INVALID_CREDENTIALS"


def test_delete_users_me_cannot_be_repeated_with_same_token(api_client: TestClient) -> None:
    _user, headers = _auth(api_client)

    assert api_client.delete(USERS_ME_URL, headers=headers).status_code == 204
    assert api_client.delete(USERS_ME_URL, headers=headers).status_code == 401


def test_delete_users_me_without_token_is_401(api_client: TestClient) -> None:
    response = api_client.delete(USERS_ME_URL)

    assert response.status_code == 401
    assert response.json() == _UNAUTHORIZED_BODY


# --------------------------------------------------------------------------- #
# Regression
# --------------------------------------------------------------------------- #


def test_health_endpoint_is_unaffected(api_client: TestClient) -> None:
    response = api_client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}
