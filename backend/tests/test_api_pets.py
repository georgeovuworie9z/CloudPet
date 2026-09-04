"""Integration tests for the pet endpoints (``/api/v1/pets``).

``POST/GET/PATCH/DELETE`` under ``/api/v1/pets``. Uses the ``api_client`` fixture
(``get_db`` overridden to the rolled-back ``db_session``). Ownership is enforced
by :class:`~app.services.pet.PetService`: a missing pet and another user's pet
both return the same 404 ``PET_NOT_FOUND``.
"""

from __future__ import annotations

from collections.abc import Iterator
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

import pytest
from app.models.pet import Pet
from app.repositories.pet import PetRepository
from app.services.exceptions import PetServiceError
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

REGISTER_URL = "/api/v1/auth/register"
LOGIN_URL = "/api/v1/auth/login"
PETS_URL = "/api/v1/pets"
PASSWORD = "s3cure-passphrase-value"

_PET_RESPONSE_FIELDS = {
    "id",
    "owner_id",
    "name",
    "species",
    "breed",
    "sex",
    "date_of_birth",
    "weight",
    "description",
    "created_at",
    "updated_at",
}

_UNAUTHORIZED_BODY: dict[str, Any] = {
    "error": {"code": "NOT_AUTHENTICATED", "message": "Not authenticated", "details": []}
}
_NOT_FOUND_BODY: dict[str, Any] = {
    "error": {"code": "PET_NOT_FOUND", "message": "Pet not found", "details": []}
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


def _pet_payload(**overrides: object) -> dict[str, Any]:
    body: dict[str, Any] = {"name": "Max", "species": "dog", "sex": "male"}
    body.update(overrides)
    return body


def _create_pet(client: TestClient, headers: dict[str, str], **overrides: object) -> dict[str, Any]:
    response = client.post(PETS_URL, headers=headers, json=_pet_payload(**overrides))
    assert response.status_code == 201
    created: dict[str, Any] = response.json()
    return created


def _create_pets(client: TestClient, headers: dict[str, str], count: int) -> list[dict[str, Any]]:
    """Create ``count`` pets for the caller; return their response bodies in creation order."""
    return [_create_pet(client, headers, name=f"pet-{i:02d}") for i in range(count)]


def _ids(body: Any) -> list[str]:
    return [str(pet["id"]) for pet in body]


# --------------------------------------------------------------------------- #
# Authentication
# --------------------------------------------------------------------------- #


def test_every_pet_endpoint_requires_authentication(api_client: TestClient) -> None:
    pet_id = uuid4()
    responses = [
        api_client.post(PETS_URL, json=_pet_payload()),
        api_client.get(PETS_URL),
        api_client.get(f"{PETS_URL}/{pet_id}"),
        api_client.patch(f"{PETS_URL}/{pet_id}", json={"name": "Rex"}),
        api_client.delete(f"{PETS_URL}/{pet_id}"),
    ]

    for response in responses:
        assert response.status_code == 401
        assert response.headers["WWW-Authenticate"] == "Bearer"
        assert response.json() == _UNAUTHORIZED_BODY


def test_invalid_token_is_401(api_client: TestClient) -> None:
    response = api_client.get(PETS_URL, headers=_bearer("not.a.valid.jwt"))

    assert response.status_code == 401
    assert response.json() == _UNAUTHORIZED_BODY


# --------------------------------------------------------------------------- #
# POST /pets
# --------------------------------------------------------------------------- #


def test_create_pet_returns_201_and_full_representation(api_client: TestClient) -> None:
    user, headers = _auth(api_client)

    response = api_client.post(
        PETS_URL,
        headers=headers,
        json=_pet_payload(
            breed="Labrador",
            date_of_birth="2022-05-12",
            weight="28.50",
            description="Good boy",
        ),
    )

    assert response.status_code == 201
    body = response.json()
    assert set(body) == _PET_RESPONSE_FIELDS
    assert body["name"] == "Max"
    assert body["species"] == "dog"
    assert body["sex"] == "male"
    assert body["breed"] == "Labrador"
    assert body["date_of_birth"] == "2022-05-12"
    assert Decimal(str(body["weight"])) == Decimal("28.50")
    assert body["description"] == "Good boy"
    assert body["owner_id"] == user["id"]
    UUID(str(body["id"]))  # parseable UUID


def test_create_pet_owner_is_the_authenticated_user(api_client: TestClient) -> None:
    user_a, headers_a = _auth(api_client, email="a@example.com")
    user_b, _headers_b = _auth(api_client, email="b@example.com")

    created = _create_pet(api_client, headers_a)

    assert created["owner_id"] == user_a["id"]
    assert created["owner_id"] != user_b["id"]


def test_create_pet_rejects_client_supplied_owner_id(api_client: TestClient) -> None:
    _user_a, headers_a = _auth(api_client, email="a@example.com")
    user_b, _headers_b = _auth(api_client, email="b@example.com")

    response = api_client.post(
        PETS_URL, headers=headers_a, json=_pet_payload(owner_id=user_b["id"])
    )

    assert response.status_code == 422
    error = response.json()["error"]
    assert error["code"] == "VALIDATION_ERROR"
    assert any(d["location"] == ["body", "owner_id"] for d in error["details"])


def test_create_pet_rejects_client_supplied_id(api_client: TestClient) -> None:
    _user, headers = _auth(api_client)

    response = api_client.post(PETS_URL, headers=headers, json=_pet_payload(id=str(uuid4())))

    assert response.status_code == 422
    error = response.json()["error"]
    assert error["code"] == "VALIDATION_ERROR"
    assert any(d["location"] == ["body", "id"] for d in error["details"])


def test_create_pet_missing_required_field_is_422(api_client: TestClient) -> None:
    _user, headers = _auth(api_client)

    for field in ("name", "species", "sex"):
        payload = _pet_payload()
        del payload[field]
        response = api_client.post(PETS_URL, headers=headers, json=payload)
        assert response.status_code == 422, field
        details = response.json()["error"]["details"]
        missing = [
            d for d in details if d["location"] == ["body", field] and d["type"] == "missing"
        ]
        assert missing, field


def test_create_pet_invalid_species_is_422(api_client: TestClient) -> None:
    _user, headers = _auth(api_client)

    response = api_client.post(PETS_URL, headers=headers, json=_pet_payload(species="dragon"))

    assert response.status_code == 422
    error = response.json()["error"]
    assert error["code"] == "VALIDATION_ERROR"
    assert any(d["location"] == ["body", "species"] for d in error["details"])


def test_create_pet_invalid_weight_is_422(api_client: TestClient) -> None:
    _user, headers = _auth(api_client)

    for bad_weight in ("0", "-1", "10000", "1.234"):
        response = api_client.post(PETS_URL, headers=headers, json=_pet_payload(weight=bad_weight))
        assert response.status_code == 422, bad_weight
        details = response.json()["error"]["details"]
        assert any(d["location"] == ["body", "weight"] for d in details), bad_weight


def test_created_pet_is_retrievable_and_listed(api_client: TestClient) -> None:
    _user, headers = _auth(api_client)

    created = _create_pet(api_client, headers)

    got = api_client.get(f"{PETS_URL}/{created['id']}", headers=headers)
    assert got.status_code == 200
    assert got.json() == created

    listed = api_client.get(PETS_URL, headers=headers)
    assert listed.status_code == 200
    assert listed.json() == [created]


# --------------------------------------------------------------------------- #
# GET /pets
# --------------------------------------------------------------------------- #


def test_list_pets_returns_only_the_callers_pets(api_client: TestClient) -> None:
    user_a, headers_a = _auth(api_client, email="a@example.com")
    _user_b, headers_b = _auth(api_client, email="b@example.com")
    a1 = _create_pet(api_client, headers_a, name="A1")
    a2 = _create_pet(api_client, headers_a, name="A2")
    _create_pet(api_client, headers_b, name="B1")

    response = api_client.get(PETS_URL, headers=headers_a)

    assert response.status_code == 200
    body = response.json()
    assert {pet["id"] for pet in body} == {a1["id"], a2["id"]}
    assert all(pet["owner_id"] == user_a["id"] for pet in body)


def test_list_pets_is_empty_for_user_with_no_pets(api_client: TestClient) -> None:
    _user, headers = _auth(api_client)

    response = api_client.get(PETS_URL, headers=headers)

    assert response.status_code == 200
    assert response.json() == []


# --------------------------------------------------------------------------- #
# GET /pets -- pagination
# --------------------------------------------------------------------------- #


def test_list_pets_default_limit_is_20(api_client: TestClient) -> None:
    _user, headers = _auth(api_client)
    _create_pets(api_client, headers, 21)

    response = api_client.get(PETS_URL, headers=headers)

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 20
    full = api_client.get(PETS_URL, headers=headers, params={"limit": 100}).json()
    assert _ids(body) == _ids(full)[:20]


def test_list_pets_default_offset_is_0(api_client: TestClient) -> None:
    _user, headers = _auth(api_client)
    _create_pets(api_client, headers, 3)

    default = api_client.get(PETS_URL, headers=headers).json()
    explicit = api_client.get(PETS_URL, headers=headers, params={"offset": 0}).json()

    assert _ids(default) == _ids(explicit)


def test_list_pets_limit_1_returns_one_item(api_client: TestClient) -> None:
    _user, headers = _auth(api_client)
    _create_pets(api_client, headers, 3)

    response = api_client.get(PETS_URL, headers=headers, params={"limit": 1})

    assert response.status_code == 200
    assert len(response.json()) == 1


def test_list_pets_limit_100_is_accepted(api_client: TestClient) -> None:
    _user, headers = _auth(api_client)
    _create_pets(api_client, headers, 5)

    response = api_client.get(PETS_URL, headers=headers, params={"limit": 100})

    assert response.status_code == 200
    assert len(response.json()) == 5


def test_list_pets_limit_0_is_422(api_client: TestClient) -> None:
    _user, headers = _auth(api_client)

    response = api_client.get(PETS_URL, headers=headers, params={"limit": 0})

    assert response.status_code == 422
    error = response.json()["error"]
    assert error["code"] == "VALIDATION_ERROR"
    assert any(d["location"] == ["query", "limit"] for d in error["details"])


def test_list_pets_limit_negative_is_422(api_client: TestClient) -> None:
    _user, headers = _auth(api_client)

    response = api_client.get(PETS_URL, headers=headers, params={"limit": -1})

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_list_pets_limit_over_100_is_422(api_client: TestClient) -> None:
    _user, headers = _auth(api_client)

    response = api_client.get(PETS_URL, headers=headers, params={"limit": 101})

    assert response.status_code == 422
    details = response.json()["error"]["details"]
    assert any(d["location"] == ["query", "limit"] for d in details)


def test_list_pets_non_integer_limit_is_422(api_client: TestClient) -> None:
    _user, headers = _auth(api_client)

    response = api_client.get(PETS_URL, headers=headers, params={"limit": "abc"})

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_list_pets_offset_negative_is_422(api_client: TestClient) -> None:
    _user, headers = _auth(api_client)

    response = api_client.get(PETS_URL, headers=headers, params={"offset": -1})

    assert response.status_code == 422
    error = response.json()["error"]
    assert error["code"] == "VALIDATION_ERROR"
    assert any(d["location"] == ["query", "offset"] for d in error["details"])


def test_list_pets_offset_skips_leading_items(api_client: TestClient) -> None:
    _user, headers = _auth(api_client)
    _create_pets(api_client, headers, 5)

    full = _ids(api_client.get(PETS_URL, headers=headers, params={"limit": 100}).json())
    page = api_client.get(PETS_URL, headers=headers, params={"limit": 100, "offset": 2})

    assert page.status_code == 200
    assert _ids(page.json()) == full[2:]


def test_list_pets_offset_beyond_collection_returns_empty(api_client: TestClient) -> None:
    _user, headers = _auth(api_client)
    _create_pets(api_client, headers, 3)

    response = api_client.get(PETS_URL, headers=headers, params={"offset": 99})

    assert response.status_code == 200
    assert response.json() == []


def test_list_pets_custom_limit_and_offset_slice(api_client: TestClient) -> None:
    _user, headers = _auth(api_client)
    _create_pets(api_client, headers, 5)

    full = _ids(api_client.get(PETS_URL, headers=headers, params={"limit": 100}).json())
    page = api_client.get(PETS_URL, headers=headers, params={"limit": 2, "offset": 2})

    assert _ids(page.json()) == full[2:4]


def test_list_pets_pages_tile_the_collection_without_overlap(api_client: TestClient) -> None:
    _user, headers = _auth(api_client)
    _create_pets(api_client, headers, 5)

    full = _ids(api_client.get(PETS_URL, headers=headers, params={"limit": 100}).json())

    collected: list[str] = []
    for offset in (0, 2, 4, 6):
        page = api_client.get(PETS_URL, headers=headers, params={"limit": 2, "offset": offset})
        assert page.status_code == 200
        collected.extend(_ids(page.json()))

    assert collected == full
    assert len(set(collected)) == len(collected)


def test_list_pets_ordering_is_stable_across_calls(api_client: TestClient) -> None:
    _user, headers = _auth(api_client)
    _create_pets(api_client, headers, 6)

    first = _ids(api_client.get(PETS_URL, headers=headers, params={"limit": 100}).json())
    second = _ids(api_client.get(PETS_URL, headers=headers, params={"limit": 100}).json())

    assert first == second


def test_list_pets_pagination_cannot_expose_another_users_pets(api_client: TestClient) -> None:
    user_a, headers_a = _auth(api_client, email="a@example.com")
    _user_b, headers_b = _auth(api_client, email="b@example.com")
    _create_pets(api_client, headers_a, 3)
    b_ids = {pet["id"] for pet in _create_pets(api_client, headers_b, 3)}

    for offset in (0, 1, 2, 3):
        page = api_client.get(PETS_URL, headers=headers_a, params={"limit": 100, "offset": offset})
        assert page.status_code == 200
        assert all(pet["owner_id"] == user_a["id"] for pet in page.json())
        assert not (b_ids & {pet["id"] for pet in page.json()})


def test_list_pets_empty_collection_with_pagination_params_returns_empty_list(
    api_client: TestClient,
) -> None:
    _user, headers = _auth(api_client)

    response = api_client.get(PETS_URL, headers=headers, params={"limit": 50, "offset": 0})

    assert response.status_code == 200
    assert response.json() == []


def test_list_pets_pagination_still_requires_authentication(api_client: TestClient) -> None:
    response = api_client.get(PETS_URL, params={"limit": 5, "offset": 5})

    assert response.status_code == 401
    assert response.headers["WWW-Authenticate"] == "Bearer"
    assert response.json() == _UNAUTHORIZED_BODY


def test_list_pets_invalid_limit_uses_the_standard_error_envelope(api_client: TestClient) -> None:
    _user, headers = _auth(api_client)

    response = api_client.get(PETS_URL, headers=headers, params={"limit": 0})

    assert response.status_code == 422
    body = response.json()
    assert set(body) == {"error"}
    assert body["error"]["code"] == "VALIDATION_ERROR"
    assert body["error"]["message"] == "Request validation failed"
    assert isinstance(body["error"]["details"], list)
    assert body["error"]["details"]


# --------------------------------------------------------------------------- #
# GET /pets/{pet_id}
# --------------------------------------------------------------------------- #


def test_get_own_pet_returns_200(api_client: TestClient) -> None:
    _user, headers = _auth(api_client)
    created = _create_pet(api_client, headers)

    response = api_client.get(f"{PETS_URL}/{created['id']}", headers=headers)

    assert response.status_code == 200
    assert response.json() == created


def test_get_nonexistent_pet_is_404_pet_not_found(api_client: TestClient) -> None:
    _user, headers = _auth(api_client)

    response = api_client.get(f"{PETS_URL}/{uuid4()}", headers=headers)

    assert response.status_code == 404
    assert response.json() == _NOT_FOUND_BODY


def test_get_another_users_pet_is_404_pet_not_found(api_client: TestClient) -> None:
    _user_a, headers_a = _auth(api_client, email="a@example.com")
    _user_b, headers_b = _auth(api_client, email="b@example.com")
    b_pet = _create_pet(api_client, headers_b)

    response = api_client.get(f"{PETS_URL}/{b_pet['id']}", headers=headers_a)

    assert response.status_code == 404
    assert response.json() == _NOT_FOUND_BODY


def test_get_nonexistent_and_cross_owner_404_bodies_are_identical(api_client: TestClient) -> None:
    _user_a, headers_a = _auth(api_client, email="a@example.com")
    _user_b, headers_b = _auth(api_client, email="b@example.com")
    b_pet = _create_pet(api_client, headers_b)

    missing = api_client.get(f"{PETS_URL}/{uuid4()}", headers=headers_a)
    cross_owner = api_client.get(f"{PETS_URL}/{b_pet['id']}", headers=headers_a)

    assert missing.status_code == cross_owner.status_code == 404
    assert missing.text == cross_owner.text


def test_get_pet_invalid_uuid_is_422_for_authenticated_request(api_client: TestClient) -> None:
    _user, headers = _auth(api_client)

    response = api_client.get(f"{PETS_URL}/not-a-uuid", headers=headers)

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


# --------------------------------------------------------------------------- #
# PATCH /pets/{pet_id}
# --------------------------------------------------------------------------- #


def test_patch_pet_updates_only_supplied_field(api_client: TestClient, db_session: Session) -> None:
    _user, headers = _auth(api_client)
    created = _create_pet(api_client, headers, breed="Labrador", description="Good boy")

    response = api_client.patch(
        f"{PETS_URL}/{created['id']}", headers=headers, json={"name": "Rex"}
    )

    assert response.status_code == 200
    body = response.json()
    assert body["name"] == "Rex"
    assert body["breed"] == "Labrador"
    assert body["description"] == "Good boy"
    assert body["species"] == created["species"]
    assert body["created_at"] == created["created_at"]

    db_session.expire_all()
    reloaded = PetRepository(db_session).get_by_id(UUID(str(created["id"])))
    assert reloaded is not None
    assert reloaded.name == "Rex"


def test_patch_pet_can_clear_nullable_fields(api_client: TestClient) -> None:
    _user, headers = _auth(api_client)
    created = _create_pet(api_client, headers, breed="Labrador", weight="28.50")
    assert created["breed"] == "Labrador"

    response = api_client.patch(
        f"{PETS_URL}/{created['id']}", headers=headers, json={"breed": None, "weight": None}
    )

    assert response.status_code == 200
    body = response.json()
    assert body["breed"] is None
    assert body["weight"] is None


def test_patch_pet_rejects_explicit_null_for_required_fields(api_client: TestClient) -> None:
    _user, headers = _auth(api_client)
    created = _create_pet(api_client, headers)

    for field in ("name", "species", "sex"):
        response = api_client.patch(
            f"{PETS_URL}/{created['id']}", headers=headers, json={field: None}
        )
        assert response.status_code == 422, field
        assert response.json()["error"]["code"] == "VALIDATION_ERROR", field


def test_patch_pet_rejects_owner_id_and_id(api_client: TestClient) -> None:
    _user, headers = _auth(api_client)
    created = _create_pet(api_client, headers)

    for forbidden in ({"owner_id": str(uuid4())}, {"id": str(uuid4())}):
        response = api_client.patch(f"{PETS_URL}/{created['id']}", headers=headers, json=forbidden)
        assert response.status_code == 422
        assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_patch_pet_empty_body_is_successful_noop(api_client: TestClient) -> None:
    _user, headers = _auth(api_client)
    created = _create_pet(api_client, headers, breed="Labrador")

    response = api_client.patch(f"{PETS_URL}/{created['id']}", headers=headers, json={})

    assert response.status_code == 200
    assert response.json() == created


def test_patch_another_users_pet_is_404_and_leaves_it_unchanged(
    api_client: TestClient, db_session: Session
) -> None:
    _user_a, headers_a = _auth(api_client, email="a@example.com")
    _user_b, headers_b = _auth(api_client, email="b@example.com")
    b_pet = _create_pet(api_client, headers_b, name="Original")

    response = api_client.patch(
        f"{PETS_URL}/{b_pet['id']}", headers=headers_a, json={"name": "Hijacked"}
    )

    assert response.status_code == 404
    assert response.json() == _NOT_FOUND_BODY

    db_session.expire_all()
    reloaded = PetRepository(db_session).get_by_id(UUID(str(b_pet["id"])))
    assert reloaded is not None
    assert reloaded.name == "Original"


def test_patch_nonexistent_pet_is_404(api_client: TestClient) -> None:
    _user, headers = _auth(api_client)

    response = api_client.patch(f"{PETS_URL}/{uuid4()}", headers=headers, json={"name": "Rex"})

    assert response.status_code == 404
    assert response.json() == _NOT_FOUND_BODY


def test_patch_pet_leaves_id_and_owner_id_unchanged(api_client: TestClient) -> None:
    _user, headers = _auth(api_client)
    created = _create_pet(api_client, headers)

    response = api_client.patch(
        f"{PETS_URL}/{created['id']}",
        headers=headers,
        json={"name": "Rex", "description": "changed"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["id"] == created["id"]
    assert body["owner_id"] == created["owner_id"]


def test_patch_pet_without_token_is_401(api_client: TestClient) -> None:
    response = api_client.patch(f"{PETS_URL}/{uuid4()}", json={"name": "Rex"})

    assert response.status_code == 401
    assert response.json() == _UNAUTHORIZED_BODY


# --------------------------------------------------------------------------- #
# DELETE /pets/{pet_id}
# --------------------------------------------------------------------------- #


def test_delete_own_pet_returns_204_empty_body(api_client: TestClient) -> None:
    _user, headers = _auth(api_client)
    created = _create_pet(api_client, headers)

    response = api_client.delete(f"{PETS_URL}/{created['id']}", headers=headers)

    assert response.status_code == 204
    assert response.content == b""


def test_delete_own_pet_actually_removes_the_row(
    api_client: TestClient, db_session: Session
) -> None:
    _user, headers = _auth(api_client)
    created = _create_pet(api_client, headers)

    api_client.delete(f"{PETS_URL}/{created['id']}", headers=headers)

    db_session.expire_all()
    assert PetRepository(db_session).get_by_id(UUID(str(created["id"]))) is None


def test_delete_pet_then_get_is_404(api_client: TestClient) -> None:
    _user, headers = _auth(api_client)
    created = _create_pet(api_client, headers)

    assert api_client.delete(f"{PETS_URL}/{created['id']}", headers=headers).status_code == 204

    response = api_client.get(f"{PETS_URL}/{created['id']}", headers=headers)
    assert response.status_code == 404
    assert response.json() == _NOT_FOUND_BODY


def test_delete_another_users_pet_is_404_and_pet_remains(
    api_client: TestClient, db_session: Session
) -> None:
    _user_a, headers_a = _auth(api_client, email="a@example.com")
    _user_b, headers_b = _auth(api_client, email="b@example.com")
    b_pet = _create_pet(api_client, headers_b)

    response = api_client.delete(f"{PETS_URL}/{b_pet['id']}", headers=headers_a)

    assert response.status_code == 404
    assert response.json() == _NOT_FOUND_BODY

    db_session.expire_all()
    assert PetRepository(db_session).get_by_id(UUID(str(b_pet["id"]))) is not None


def test_delete_nonexistent_pet_is_404(api_client: TestClient) -> None:
    _user, headers = _auth(api_client)

    response = api_client.delete(f"{PETS_URL}/{uuid4()}", headers=headers)

    assert response.status_code == 404
    assert response.json() == _NOT_FOUND_BODY


def test_delete_pet_twice_second_call_is_404(api_client: TestClient) -> None:
    _user, headers = _auth(api_client)
    created = _create_pet(api_client, headers)

    assert api_client.delete(f"{PETS_URL}/{created['id']}", headers=headers).status_code == 204
    assert api_client.delete(f"{PETS_URL}/{created['id']}", headers=headers).status_code == 404


# --------------------------------------------------------------------------- #
# Error envelope
# --------------------------------------------------------------------------- #


def test_pet_not_found_uses_the_standard_404_envelope(api_client: TestClient) -> None:
    _user, headers = _auth(api_client)

    response = api_client.get(f"{PETS_URL}/{uuid4()}", headers=headers)

    assert response.status_code == 404
    body = response.json()
    assert body == _NOT_FOUND_BODY
    assert body["error"]["details"] == []
    assert body["error"]["message"] == "Pet not found"


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
        email="fake@example.com",
        password_hash="x",
        first_name="Fake",
        last_name="User",
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


def test_unmapped_pet_service_error_returns_500_envelope(
    pet_service_error_client: TestClient,
) -> None:
    response = pet_service_error_client.get(PETS_URL)

    assert response.status_code == 500
    body = response.json()
    assert body["error"]["code"] == "INTERNAL_SERVER_ERROR"
    assert body["error"]["details"] == []
    assert "internal detail that must not leak" not in response.text


# --------------------------------------------------------------------------- #
# Hardening -- regression locks
# --------------------------------------------------------------------------- #


def test_patch_pet_invalid_uuid_is_422_for_authenticated_request(api_client: TestClient) -> None:
    _user, headers = _auth(api_client)

    response = api_client.patch(f"{PETS_URL}/not-a-uuid", headers=headers, json={"name": "Rex"})

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_delete_pet_invalid_uuid_is_422_for_authenticated_request(api_client: TestClient) -> None:
    _user, headers = _auth(api_client)

    response = api_client.delete(f"{PETS_URL}/not-a-uuid", headers=headers)

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_put_on_a_pet_item_is_405_method_not_allowed(api_client: TestClient) -> None:
    _user, headers = _auth(api_client)
    created = _create_pet(api_client, headers)

    response = api_client.put(f"{PETS_URL}/{created['id']}", headers=headers, json={"name": "Rex"})

    assert response.status_code == 405
    assert response.json()["error"]["code"] == "METHOD_NOT_ALLOWED"


def test_unauthenticated_malformed_uuid_is_401_not_422(api_client: TestClient) -> None:
    # The auth dependency resolves before path validation, so an unauthenticated
    # caller never learns whether the path was well-formed.
    response = api_client.get(f"{PETS_URL}/not-a-uuid")

    assert response.status_code == 401
    assert response.json() == _UNAUTHORIZED_BODY


def test_unauthenticated_invalid_query_param_is_401_not_422(api_client: TestClient) -> None:
    response = api_client.get(PETS_URL, params={"limit": 0})

    assert response.status_code == 401
    assert response.json() == _UNAUTHORIZED_BODY


# --------------------------------------------------------------------------- #
# Regression
# --------------------------------------------------------------------------- #


def test_health_endpoint_is_unaffected(api_client: TestClient) -> None:
    response = api_client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}
