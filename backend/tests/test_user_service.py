"""Service-layer tests — run against the real PostgreSQL test database.

The service is exercised end to end with a real ``UserRepository`` and
``db_session`` (rolled back per test). No mocking: it is the simplest faithful
strategy here, and ``UserService(session, repository=...)`` still allows a repo
mock later if business logic ever needs isolating.
"""

from __future__ import annotations

from uuid import uuid4

import pytest
from app.core.security import verify_password
from app.repositories.user import UserRepository
from app.schemas.auth import LoginRequest, UserCreate
from app.schemas.user import UserUpdate
from app.services.exceptions import (
    DuplicateEmailError,
    InvalidCredentialsError,
    InvalidProfileUpdateError,
    UserNotFoundError,
)
from app.services.user import UserService
from sqlalchemy.orm import Session

PASSWORD = "s3cure-passphrase-value"


def _registration(**overrides: object) -> UserCreate:
    data: dict[str, object] = {
        "email": "george@example.com",
        "password": PASSWORD,
        "first_name": "George",
        "last_name": "Ovuworie",
        "phone": None,
    }
    data.update(overrides)
    return UserCreate(**data)


@pytest.fixture
def service(db_session: Session) -> UserService:
    return UserService(db_session)


# --------------------------------------------------------------------------- #
# Registration
# --------------------------------------------------------------------------- #


def test_register_returns_persisted_user(db_session: Session, service: UserService) -> None:
    user = service.register(_registration(phone="+45 11 22 33 44"))

    assert user.id is not None
    assert user.email == "george@example.com"
    assert user.first_name == "George"
    assert user.last_name == "Ovuworie"
    assert user.phone == "+45 11 22 33 44"
    assert user.is_active is True
    assert user.created_at.tzinfo is not None
    assert user.updated_at.tzinfo is not None

    db_session.expire_all()
    assert UserRepository(db_session).get_by_id(user.id) is not None


def test_register_stores_argon2id_hash(service: UserService) -> None:
    user = service.register(_registration())

    assert user.password_hash.startswith("$argon2id$")
    assert user.password_hash != PASSWORD
    assert verify_password(PASSWORD, user.password_hash) is True


def test_register_rejects_duplicate_email(service: UserService) -> None:
    service.register(_registration())

    with pytest.raises(DuplicateEmailError):
        service.register(_registration(first_name="Someone", last_name="Else"))


def test_register_persists_normalized_email(db_session: Session, service: UserService) -> None:
    registration = _registration(email="  George@Example.COM  ")
    assert registration.email == "george@example.com"  # normalised by the schema

    user = service.register(registration)

    assert user.email == "george@example.com"
    db_session.expire_all()
    assert UserRepository(db_session).get_by_email("george@example.com") is not None


def test_register_does_not_expose_plaintext_password(service: UserService) -> None:
    user = service.register(_registration())

    assert not hasattr(user, "password")


# --------------------------------------------------------------------------- #
# Authentication
# --------------------------------------------------------------------------- #


def test_authenticate_succeeds_with_correct_credentials(service: UserService) -> None:
    registered = service.register(_registration())

    authenticated = service.authenticate(
        LoginRequest(email="george@example.com", password=PASSWORD)
    )

    assert authenticated.id == registered.id


def test_authenticate_unknown_email_fails_generically(service: UserService) -> None:
    with pytest.raises(InvalidCredentialsError):
        service.authenticate(LoginRequest(email="ghost@example.com", password=PASSWORD))


def test_authenticate_wrong_password_fails_generically(service: UserService) -> None:
    service.register(_registration())

    with pytest.raises(InvalidCredentialsError):
        service.authenticate(LoginRequest(email="george@example.com", password="not-the-password"))


def test_authenticate_inactive_user_fails_generically(service: UserService) -> None:
    user = service.register(_registration())
    service.deactivate(user.id)

    with pytest.raises(InvalidCredentialsError):
        service.authenticate(LoginRequest(email="george@example.com", password=PASSWORD))


def test_authenticate_inactive_user_with_correct_password_still_fails(
    service: UserService,
) -> None:
    user = service.register(_registration())
    service.deactivate(user.id)

    with pytest.raises(InvalidCredentialsError):
        service.authenticate(LoginRequest(email="george@example.com", password=PASSWORD))


def test_authentication_failure_modes_are_indistinguishable(
    db_session: Session,
) -> None:
    messages: set[str] = set()

    # unknown email
    svc = UserService(db_session)
    with pytest.raises(InvalidCredentialsError) as unknown:
        svc.authenticate(LoginRequest(email="ghost@example.com", password=PASSWORD))
    messages.add(str(unknown.value))

    # wrong password
    svc.register(_registration())
    with pytest.raises(InvalidCredentialsError) as wrong:
        svc.authenticate(LoginRequest(email="george@example.com", password="wrong-one"))
    messages.add(str(wrong.value))

    # inactive account, correct password
    user = svc.register(_registration(email="inactive@example.com"))
    svc.deactivate(user.id)
    with pytest.raises(InvalidCredentialsError) as inactive:
        svc.authenticate(LoginRequest(email="inactive@example.com", password=PASSWORD))
    messages.add(str(inactive.value))

    assert len(messages) == 1


# --------------------------------------------------------------------------- #
# Profile update
# --------------------------------------------------------------------------- #


def test_update_profile_changes_only_supplied_fields(service: UserService) -> None:
    user = service.register(_registration(phone="+45 11 22 33 44"))

    updated = service.update_profile(user.id, UserUpdate(first_name="Georgina"))

    assert updated.first_name == "Georgina"
    assert updated.last_name == "Ovuworie"
    assert updated.phone == "+45 11 22 33 44"
    assert updated.email == "george@example.com"


def test_update_profile_preserves_omitted_fields_in_db(
    db_session: Session, service: UserService
) -> None:
    user = service.register(_registration(phone="+45 11 22 33 44"))

    service.update_profile(user.id, UserUpdate(last_name="Renamed"))

    db_session.expire_all()
    reloaded = UserRepository(db_session).get_by_id(user.id)
    assert reloaded is not None
    assert reloaded.first_name == "George"
    assert reloaded.phone == "+45 11 22 33 44"
    assert reloaded.last_name == "Renamed"


def test_update_profile_cannot_receive_email_field() -> None:
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        UserUpdate.model_validate({"email": "new@example.com"})


def test_update_profile_rejects_explicit_null_first_name(
    db_session: Session, service: UserService
) -> None:
    user = service.register(_registration())

    with pytest.raises(InvalidProfileUpdateError):
        service.update_profile(user.id, UserUpdate(first_name=None))

    db_session.expire_all()
    reloaded = UserRepository(db_session).get_by_id(user.id)
    assert reloaded is not None
    assert reloaded.first_name == "George"


def test_update_profile_rejects_explicit_null_last_name(service: UserService) -> None:
    user = service.register(_registration())

    with pytest.raises(InvalidProfileUpdateError):
        service.update_profile(user.id, UserUpdate(last_name=None))


def test_update_profile_allows_explicit_null_phone(
    db_session: Session, service: UserService
) -> None:
    user = service.register(_registration(phone="+45 11 22 33 44"))

    updated = service.update_profile(user.id, UserUpdate(phone=None))

    assert updated.phone is None
    db_session.expire_all()
    reloaded = UserRepository(db_session).get_by_id(user.id)
    assert reloaded is not None
    assert reloaded.phone is None


def test_update_profile_unknown_user_raises(service: UserService) -> None:
    with pytest.raises(UserNotFoundError):
        service.update_profile(uuid4(), UserUpdate(first_name="Nobody"))


def test_update_profile_does_not_touch_is_active_or_created_at(service: UserService) -> None:
    user = service.register(_registration())
    created_at = user.created_at

    updated = service.update_profile(user.id, UserUpdate(first_name="Georgina"))

    assert updated.is_active is True
    assert updated.created_at == created_at


def test_update_profile_empty_payload_is_a_noop(service: UserService) -> None:
    user = service.register(_registration())

    updated = service.update_profile(user.id, UserUpdate())

    assert updated.id == user.id
    assert updated.first_name == "George"


# --------------------------------------------------------------------------- #
# Deactivation
# --------------------------------------------------------------------------- #


def test_deactivate_marks_user_inactive(service: UserService) -> None:
    user = service.register(_registration())

    deactivated = service.deactivate(user.id)

    assert deactivated.is_active is False


def test_deactivate_keeps_the_row(db_session: Session, service: UserService) -> None:
    user = service.register(_registration())

    service.deactivate(user.id)

    db_session.expire_all()
    reloaded = UserRepository(db_session).get_by_id(user.id)
    assert reloaded is not None
    assert reloaded.is_active is False


def test_deactivate_is_idempotent(db_session: Session, service: UserService) -> None:
    user = service.register(_registration())

    service.deactivate(user.id)
    again = service.deactivate(user.id)

    assert again.is_active is False
    db_session.expire_all()
    assert UserRepository(db_session).get_by_id(user.id) is not None


def test_deactivate_unknown_user_raises(service: UserService) -> None:
    with pytest.raises(UserNotFoundError):
        service.deactivate(uuid4())
