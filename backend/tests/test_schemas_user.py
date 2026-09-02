"""Unit tests for the user resource schemas (no database)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta, timezone
from uuid import UUID, uuid4

import pytest
from app.models.user import User
from app.schemas.user import UserResponse, UserUpdate
from pydantic import ValidationError


def _make_user(**overrides: object) -> User:
    """An in-memory ``User`` ORM instance (never added to a session)."""
    defaults: dict[str, object] = {
        "id": uuid4(),
        "email": "george@example.com",
        "password_hash": "$argon2id$v=19$m=65536,t=3,p=4$c2FsdHNhbHQ$aGFzaGhhc2g",
        "first_name": "George",
        "last_name": "Ovuworie",
        "phone": None,
        "is_active": True,
        "created_at": datetime(2026, 9, 1, 12, 0, tzinfo=UTC),
        "updated_at": datetime(2026, 9, 2, 12, 0, tzinfo=UTC),
    }
    defaults.update(overrides)
    return User(**defaults)


class TestUserResponse:
    def test_valid_uuid_is_accepted(self) -> None:
        user_id = uuid4()
        response = UserResponse.model_validate(_make_user(id=user_id))

        assert response.id == user_id
        assert isinstance(response.id, UUID)

    def test_uuid_string_is_coerced(self) -> None:
        response = UserResponse.model_validate(
            _make_user(id="12345678-1234-5678-1234-567812345678")
        )

        assert response.id == UUID("12345678-1234-5678-1234-567812345678")

    def test_timezone_aware_timestamps_are_accepted(self) -> None:
        created = datetime(2026, 1, 1, 9, 30, tzinfo=timezone(timedelta(hours=2)))
        updated = datetime(2026, 1, 2, 9, 30, tzinfo=UTC)

        response = UserResponse.model_validate(_make_user(created_at=created, updated_at=updated))

        assert response.created_at == created
        assert response.updated_at == updated
        assert response.created_at.tzinfo is not None

    def test_naive_timestamps_are_rejected(self) -> None:
        with pytest.raises(ValidationError):
            UserResponse.model_validate(_make_user(created_at=datetime(2026, 1, 1, 9, 30)))

    def test_orm_object_serialization_round_trips(self) -> None:
        user = _make_user(phone="+45 12 34 56 78", is_active=False)

        response = UserResponse.model_validate(user)
        dumped = response.model_dump()

        assert dumped["id"] == user.id
        assert dumped["email"] == "george@example.com"
        assert dumped["first_name"] == "George"
        assert dumped["last_name"] == "Ovuworie"
        assert dumped["phone"] == "+45 12 34 56 78"
        assert dumped["is_active"] is False
        assert dumped["created_at"] == user.created_at
        assert dumped["updated_at"] == user.updated_at

    def test_password_hash_is_never_exposed(self) -> None:
        user = _make_user()

        response = UserResponse.model_validate(user)

        assert "password_hash" not in response.model_dump()
        assert "password_hash" not in response.model_dump_json()
        assert not hasattr(response, "password_hash")


class TestUserUpdate:
    @pytest.mark.parametrize(
        ("field", "value"),
        [
            ("first_name", "Georgina"),
            ("last_name", "Newname"),
            ("phone", "+45 99 99 99 99"),
        ],
    )
    def test_each_field_can_be_updated_independently(self, field: str, value: str) -> None:
        update = UserUpdate.model_validate({field: value})

        assert update.model_dump(exclude_unset=True) == {field: value}

    def test_empty_update_is_a_valid_no_op(self) -> None:
        update = UserUpdate()

        assert update.model_dump(exclude_unset=True) == {}

    def test_explicit_none_is_distinct_from_omitted(self) -> None:
        assert UserUpdate(phone=None).model_dump(exclude_unset=True) == {"phone": None}
        assert UserUpdate().model_dump(exclude_unset=True) == {}

    def test_names_are_trimmed(self) -> None:
        update = UserUpdate(first_name="  Georgina  ")

        assert update.first_name == "Georgina"

    @pytest.mark.parametrize(
        "field",
        [
            "email",
            "is_active",
            "password",
            "password_hash",
            "id",
            "created_at",
            "updated_at",
        ],
    )
    def test_disallowed_field_is_rejected(self, field: str) -> None:
        with pytest.raises(ValidationError):
            UserUpdate.model_validate({field: "whatever"})

    def test_unknown_field_is_rejected(self) -> None:
        with pytest.raises(ValidationError):
            UserUpdate.model_validate({"nickname": "gg"})
