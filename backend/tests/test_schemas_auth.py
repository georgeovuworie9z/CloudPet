"""Unit tests for the auth request/response schemas (no database)."""

from __future__ import annotations

import pytest
from app.schemas.auth import LoginRequest, TokenResponse, UserCreate
from pydantic import ValidationError

VALID_PASSWORD = "a" * 12


def _user_create_kwargs(**overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "email": "george@example.com",
        "password": VALID_PASSWORD,
        "first_name": "George",
        "last_name": "Ovuworie",
    }
    base.update(overrides)
    return base


class TestUserCreate:
    def test_valid_registration_data(self) -> None:
        user = UserCreate(**_user_create_kwargs(phone="+45 12 34 56 78"))

        assert user.email == "george@example.com"
        assert user.password == VALID_PASSWORD
        assert user.first_name == "George"
        assert user.last_name == "Ovuworie"
        assert user.phone == "+45 12 34 56 78"

    def test_email_is_normalised_to_trimmed_lowercase(self) -> None:
        user = UserCreate(**_user_create_kwargs(email="  George@Example.COM  "))

        assert user.email == "george@example.com"

    def test_names_are_trimmed(self) -> None:
        user = UserCreate(**_user_create_kwargs(first_name="  George  ", last_name="  O  "))

        assert user.first_name == "George"
        assert user.last_name == "O"

    def test_password_of_exactly_12_is_accepted(self) -> None:
        user = UserCreate(**_user_create_kwargs(password="x" * 12))

        assert len(user.password) == 12

    def test_password_of_exactly_128_is_accepted(self) -> None:
        user = UserCreate(**_user_create_kwargs(password="x" * 128))

        assert len(user.password) == 128

    def test_password_shorter_than_12_is_rejected(self) -> None:
        with pytest.raises(ValidationError):
            UserCreate(**_user_create_kwargs(password="x" * 11))

    def test_password_longer_than_128_is_rejected(self) -> None:
        with pytest.raises(ValidationError):
            UserCreate(**_user_create_kwargs(password="x" * 129))

    def test_invalid_email_is_rejected(self) -> None:
        with pytest.raises(ValidationError):
            UserCreate(**_user_create_kwargs(email="not-an-email"))

    @pytest.mark.parametrize("missing", ["email", "password", "first_name", "last_name"])
    def test_missing_required_field_is_rejected(self, missing: str) -> None:
        kwargs = _user_create_kwargs()
        del kwargs[missing]

        with pytest.raises(ValidationError):
            UserCreate(**kwargs)

    @pytest.mark.parametrize("field", ["is_active", "password_hash", "id", "created_at"])
    def test_unexpected_field_is_rejected(self, field: str) -> None:
        with pytest.raises(ValidationError):
            UserCreate(**_user_create_kwargs(**{field: "whatever"}))

    def test_phone_is_optional_and_defaults_to_none(self) -> None:
        user = UserCreate(**_user_create_kwargs())

        assert user.phone is None

    def test_blank_phone_is_rejected(self) -> None:
        with pytest.raises(ValidationError):
            UserCreate(**_user_create_kwargs(phone="   "))


class TestLoginRequest:
    def test_valid_login_data(self) -> None:
        login = LoginRequest(email="george@example.com", password="whatever-they-typed")

        assert login.email == "george@example.com"
        assert login.password == "whatever-they-typed"

    def test_email_is_normalised_consistently_with_registration(self) -> None:
        login = LoginRequest(email="  George@Example.COM  ", password="pw")

        assert login.email == "george@example.com"

    def test_invalid_email_is_rejected(self) -> None:
        with pytest.raises(ValidationError):
            LoginRequest(email="nope", password="pw")

    @pytest.mark.parametrize("missing", ["email", "password"])
    def test_missing_field_is_rejected(self, missing: str) -> None:
        kwargs = {"email": "george@example.com", "password": "pw"}
        del kwargs[missing]

        with pytest.raises(ValidationError):
            LoginRequest(**kwargs)

    def test_empty_password_is_rejected(self) -> None:
        with pytest.raises(ValidationError):
            LoginRequest(email="george@example.com", password="")

    def test_unexpected_field_is_rejected(self) -> None:
        with pytest.raises(ValidationError):
            LoginRequest.model_validate(
                {"email": "george@example.com", "password": "pw", "remember_me": True}
            )


class TestTokenResponse:
    def test_default_representation(self) -> None:
        token = TokenResponse(access_token="header.payload.signature")

        assert token.model_dump() == {
            "access_token": "header.payload.signature",
            "token_type": "bearer",
        }

    def test_token_type_can_be_set_explicitly(self) -> None:
        token = TokenResponse(access_token="abc", token_type="bearer")

        assert token.token_type == "bearer"
