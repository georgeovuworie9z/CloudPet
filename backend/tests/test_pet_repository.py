"""Repository tests for :class:`~app.repositories.pet.PetRepository`.

Run against the real PostgreSQL test database via the ``db_session`` fixture,
which wraps each test in a transaction that is rolled back afterwards. No mocks.
Follows the patterns established by ``test_user_repository.py``.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from app.models.pet import Pet
from app.models.user import User
from app.repositories.pet import PetRepository
from sqlalchemy.orm import Session

_HASH = "$argon2id$v=19$m=65536,t=3,p=4$c2FsdHNhbHRzYWx0$aGFzaGhhc2hoYXNoaGFzaA"


@pytest.fixture
def repository(db_session: Session) -> PetRepository:
    return PetRepository(db_session)


def _make_user(db_session: Session, email: str = "owner@example.com") -> User:
    user = User(
        email=email,
        password_hash=_HASH,
        first_name="George",
        last_name="Ovuworie",
    )
    db_session.add(user)
    db_session.flush()
    return user


def _make_pet(owner_id: UUID, **overrides: object) -> Pet:
    data: dict[str, object] = {
        "owner_id": owner_id,
        "name": "Max",
        "species": "dog",
        "sex": "male",
    }
    data.update(overrides)
    return Pet(**data)


def test_create_assigns_uuid_and_row_is_retrievable(
    db_session: Session, repository: PetRepository
) -> None:
    owner = _make_user(db_session)
    pet = repository.create(_make_pet(owner.id))
    db_session.commit()
    pet_id = pet.id
    db_session.expire_all()

    fetched = repository.get_by_id(pet_id)

    assert fetched is not None
    assert isinstance(fetched.id, UUID)
    assert fetched.id == pet_id
    assert fetched.owner_id == owner.id
    assert fetched.name == "Max"
    assert fetched.created_at.tzinfo is not None
    assert fetched.updated_at.tzinfo is not None


def test_get_by_id_returns_none_for_unknown_id(repository: PetRepository) -> None:
    assert repository.get_by_id(uuid4()) is None


def test_create_flushes_but_does_not_commit(db_session: Session, repository: PetRepository) -> None:
    owner = _make_user(db_session)
    pet = repository.create(_make_pet(owner.id))
    pet_id = pet.id

    # The repository only flushed; a rollback must undo the INSERT.
    db_session.rollback()

    assert repository.get_by_id(pet_id) is None


def test_get_by_id_ignores_ownership(db_session: Session, repository: PetRepository) -> None:
    owner = _make_user(db_session, email="real-owner@example.com")
    pet = repository.create(_make_pet(owner.id))
    db_session.commit()

    # get_by_id takes no owner argument -- ownership enforcement is the service's job.
    fetched = repository.get_by_id(pet.id)

    assert fetched is not None
    assert fetched.owner_id == owner.id


def test_list_by_owner_returns_only_that_owners_pets(
    db_session: Session, repository: PetRepository
) -> None:
    owner_a = _make_user(db_session, email="a@example.com")
    owner_b = _make_user(db_session, email="b@example.com")
    repository.create(_make_pet(owner_a.id, name="A1"))
    repository.create(_make_pet(owner_a.id, name="A2"))
    repository.create(_make_pet(owner_b.id, name="B1"))
    db_session.commit()

    pets_a = repository.list_by_owner(owner_a.id)

    assert {pet.name for pet in pets_a} == {"A1", "A2"}
    assert all(pet.owner_id == owner_a.id for pet in pets_a)


def test_list_by_owner_is_empty_for_owner_with_no_pets(repository: PetRepository) -> None:
    assert not repository.list_by_owner(uuid4())


def test_list_by_owner_orders_by_created_at_ascending(
    db_session: Session, repository: PetRepository
) -> None:
    owner = _make_user(db_session)
    early = datetime(2020, 1, 1, tzinfo=UTC)
    middle = datetime(2021, 1, 1, tzinfo=UTC)
    late = datetime(2022, 1, 1, tzinfo=UTC)
    # Inserted out of chronological order.
    repository.create(_make_pet(owner.id, name="middle", created_at=middle))
    repository.create(_make_pet(owner.id, name="late", created_at=late))
    repository.create(_make_pet(owner.id, name="early", created_at=early))
    db_session.commit()

    names = [pet.name for pet in repository.list_by_owner(owner.id)]

    assert names == ["early", "middle", "late"]


def test_save_persists_a_field_change(db_session: Session, repository: PetRepository) -> None:
    owner = _make_user(db_session)
    pet = repository.create(_make_pet(owner.id))
    db_session.commit()
    pet_id = pet.id

    pet.name = "Rex"
    repository.save(pet)
    db_session.commit()
    db_session.expire_all()

    reloaded = repository.get_by_id(pet_id)
    assert reloaded is not None
    assert reloaded.name == "Rex"


def test_delete_removes_the_row(db_session: Session, repository: PetRepository) -> None:
    owner = _make_user(db_session)
    pet = repository.create(_make_pet(owner.id))
    db_session.commit()
    pet_id = pet.id

    repository.delete(pet)
    db_session.commit()
    db_session.expire_all()

    assert repository.get_by_id(pet_id) is None


def test_delete_flushes_but_does_not_commit(db_session: Session, repository: PetRepository) -> None:
    owner = _make_user(db_session)
    pet = repository.create(_make_pet(owner.id))
    db_session.commit()
    pet_id = pet.id

    repository.delete(pet)
    # The repository only flushed the DELETE; a rollback must restore the row.
    db_session.rollback()

    assert repository.get_by_id(pet_id) is not None


def test_nullable_fields_persist_as_none(db_session: Session, repository: PetRepository) -> None:
    owner = _make_user(db_session)
    pet = repository.create(_make_pet(owner.id))
    db_session.commit()
    pet_id = pet.id
    db_session.expire_all()

    reloaded = repository.get_by_id(pet_id)
    assert reloaded is not None
    assert reloaded.breed is None
    assert reloaded.date_of_birth is None
    assert reloaded.weight is None
    assert reloaded.description is None


def test_decimal_weight_is_preserved(db_session: Session, repository: PetRepository) -> None:
    owner = _make_user(db_session)
    pet = repository.create(_make_pet(owner.id, weight=Decimal("28.50")))
    db_session.commit()
    pet_id = pet.id
    db_session.expire_all()

    reloaded = repository.get_by_id(pet_id)
    assert reloaded is not None
    assert reloaded.weight == Decimal("28.50")
    assert isinstance(reloaded.weight, Decimal)
    assert not isinstance(reloaded.weight, float)


def test_isolation_between_tests_part_1(db_session: Session, repository: PetRepository) -> None:
    owner = _make_user(db_session, email="iso@example.com")
    repository.create(_make_pet(owner.id, name="iso-pet"))
    db_session.commit()

    assert len(repository.list_by_owner(owner.id)) == 1


def test_isolation_between_tests_part_2(db_session: Session, repository: PetRepository) -> None:
    # Re-uses the same owner email; a unique-constraint error here would mean
    # part 1's row leaked.
    owner = _make_user(db_session, email="iso@example.com")
    assert not repository.list_by_owner(owner.id)

    repository.create(_make_pet(owner.id, name="iso-pet"))
    db_session.commit()

    assert len(repository.list_by_owner(owner.id)) == 1
