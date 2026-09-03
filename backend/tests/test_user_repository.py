"""Repository tests — run against the real PostgreSQL test database.

Every test uses the ``db_session`` fixture, which wraps the test in a
transaction that is rolled back afterwards, so nothing leaks between tests.
"""

from __future__ import annotations

from uuid import uuid4

import pytest
from app.models.user import User
from app.repositories.user import UserRepository
from sqlalchemy.orm import Session

_HASH = "$argon2id$v=19$m=65536,t=3,p=4$c2FsdHNhbHRzYWx0$aGFzaGhhc2hoYXNoaGFzaA"


def _make_user(**overrides: object) -> User:
    data: dict[str, object] = {
        "email": "george@example.com",
        "password_hash": _HASH,
        "first_name": "George",
        "last_name": "Ovuworie",
        "phone": None,
    }
    data.update(overrides)
    return User(**data)


@pytest.fixture
def repository(db_session: Session) -> UserRepository:
    return UserRepository(db_session)


def test_create_assigns_uuid_and_row_is_retrievable(
    db_session: Session, repository: UserRepository
) -> None:
    user = repository.create(_make_user())
    db_session.commit()
    user_id = user.id
    db_session.expire_all()

    fetched = repository.get_by_id(user_id)

    assert fetched is not None
    assert fetched.id == user_id
    assert fetched.email == "george@example.com"
    assert fetched.is_active is True
    assert fetched.created_at.tzinfo is not None
    assert fetched.updated_at.tzinfo is not None


def test_get_by_id_returns_none_for_unknown_id(repository: UserRepository) -> None:
    assert repository.get_by_id(uuid4()) is None


def test_get_by_email_returns_the_matching_user(
    db_session: Session, repository: UserRepository
) -> None:
    created = repository.create(_make_user(email="lookup@example.com"))
    db_session.commit()

    found = repository.get_by_email("lookup@example.com")

    assert found is not None
    assert found.id == created.id


def test_get_by_email_returns_none_for_unknown_email(repository: UserRepository) -> None:
    assert repository.get_by_email("nobody@example.com") is None


def test_get_by_email_is_an_exact_match(db_session: Session, repository: UserRepository) -> None:
    repository.create(_make_user(email="exact@example.com"))
    db_session.commit()

    # The repository does not normalise; that is the schema/service's job.
    assert repository.get_by_email("EXACT@EXAMPLE.COM") is None


def test_save_persists_a_field_change(db_session: Session, repository: UserRepository) -> None:
    user = repository.create(_make_user())
    db_session.commit()
    user_id = user.id

    user.first_name = "Georgina"
    repository.save(user)
    db_session.commit()
    db_session.expire_all()

    reloaded = repository.get_by_id(user_id)
    assert reloaded is not None
    assert reloaded.first_name == "Georgina"


def test_deactivate_clears_flag_and_keeps_the_row(
    db_session: Session, repository: UserRepository
) -> None:
    user = repository.create(_make_user())
    db_session.commit()
    user_id = user.id

    repository.deactivate(user)
    assert user.is_active is False
    db_session.commit()
    db_session.expire_all()

    reloaded = repository.get_by_id(user_id)
    assert reloaded is not None
    assert reloaded.is_active is False


def test_create_flushes_but_does_not_commit(
    db_session: Session, repository: UserRepository
) -> None:
    user = repository.create(_make_user(email="uncommitted@example.com"))
    user_id = user.id

    # The repository only flushed; a rollback must undo the INSERT.
    db_session.rollback()

    assert repository.get_by_id(user_id) is None


def test_isolation_between_tests_part_1(db_session: Session, repository: UserRepository) -> None:
    repository.create(_make_user(email="shared@example.com"))
    db_session.commit()

    assert repository.get_by_email("shared@example.com") is not None


def test_isolation_between_tests_part_2(db_session: Session, repository: UserRepository) -> None:
    # Would raise a unique-constraint error if part 1's row had leaked.
    assert repository.get_by_email("shared@example.com") is None

    repository.create(_make_user(email="shared@example.com"))
    db_session.commit()

    assert repository.get_by_email("shared@example.com") is not None
