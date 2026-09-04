"""Service-layer tests for :class:`~app.services.pet.PetService`.

Run against the real PostgreSQL test database via the ``db_session`` fixture
(one transaction per test, rolled back afterwards). No mocks. Follows the
patterns established by ``test_user_service.py``.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from app.models.user import User
from app.repositories.pet import PetRepository
from app.schemas.pet import PetCreate, PetUpdate
from app.services.exceptions import PetNotFoundError
from app.services.pet import PetService
from sqlalchemy.orm import Session

_HASH = "$argon2id$v=19$m=65536,t=3,p=4$c2FsdHNhbHRzYWx0$aGFzaGhhc2hoYXNoaGFzaA"


@pytest.fixture
def service(db_session: Session) -> PetService:
    return PetService(db_session)


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


def _pet_create(**overrides: object) -> PetCreate:
    data: dict[str, object] = {"name": "Max", "species": "dog", "sex": "male"}
    data.update(overrides)
    return PetCreate(**data)


# --------------------------------------------------------------------------- #
# create
# --------------------------------------------------------------------------- #


def test_create_persists_pet_owned_by_the_given_owner(
    db_session: Session, service: PetService
) -> None:
    owner = _make_user(db_session)

    pet = service.create(
        owner.id,
        _pet_create(
            breed="Labrador",
            date_of_birth=date(2022, 5, 12),
            weight=Decimal("28.50"),
            description="Friendly.",
        ),
    )

    assert isinstance(pet.id, UUID)
    assert pet.owner_id == owner.id
    assert pet.name == "Max"
    assert pet.species == "dog"
    assert pet.sex == "male"
    assert pet.breed == "Labrador"
    assert pet.date_of_birth == date(2022, 5, 12)
    assert pet.weight == Decimal("28.50")
    assert pet.description == "Friendly."
    assert pet.created_at.tzinfo is not None
    assert pet.updated_at.tzinfo is not None

    db_session.expire_all()
    reloaded = PetRepository(db_session).get_by_id(pet.id)
    assert reloaded is not None
    assert reloaded.owner_id == owner.id


def test_create_assigns_the_owner_from_the_argument(
    db_session: Session, service: PetService
) -> None:
    owner_a = _make_user(db_session, email="a@example.com")
    owner_b = _make_user(db_session, email="b@example.com")

    pet = service.create(owner_b.id, _pet_create())

    assert pet.owner_id == owner_b.id
    assert pet.owner_id != owner_a.id


def test_create_is_committed(db_session: Session, service: PetService) -> None:
    owner = _make_user(db_session)
    pet = service.create(owner.id, _pet_create())
    pet_id = pet.id

    # The service committed; a rollback must NOT undo it.
    db_session.rollback()

    assert PetRepository(db_session).get_by_id(pet_id) is not None


# --------------------------------------------------------------------------- #
# get + ownership
# --------------------------------------------------------------------------- #


def test_get_returns_the_owners_pet(db_session: Session, service: PetService) -> None:
    owner = _make_user(db_session)
    created = service.create(owner.id, _pet_create())

    fetched = service.get(created.id, owner.id)

    assert fetched.id == created.id
    assert fetched.owner_id == owner.id


def test_get_nonexistent_pet_raises_not_found(db_session: Session, service: PetService) -> None:
    owner = _make_user(db_session)

    with pytest.raises(PetNotFoundError):
        service.get(uuid4(), owner.id)


def test_get_other_owners_pet_raises_not_found(db_session: Session, service: PetService) -> None:
    owner_a = _make_user(db_session, email="a@example.com")
    owner_b = _make_user(db_session, email="b@example.com")
    pet = service.create(owner_a.id, _pet_create())

    with pytest.raises(PetNotFoundError):
        service.get(pet.id, owner_b.id)


def test_missing_and_not_owned_are_indistinguishable(
    db_session: Session, service: PetService
) -> None:
    owner_a = _make_user(db_session, email="a@example.com")
    owner_b = _make_user(db_session, email="b@example.com")
    pet = service.create(owner_a.id, _pet_create())

    with pytest.raises(PetNotFoundError) as missing:
        service.get(uuid4(), owner_b.id)
    with pytest.raises(PetNotFoundError) as not_owned:
        service.get(pet.id, owner_b.id)

    assert type(missing.value) is PetNotFoundError
    assert type(missing.value) is type(not_owned.value)


# --------------------------------------------------------------------------- #
# list_for_owner
# --------------------------------------------------------------------------- #


def test_list_for_owner_returns_only_that_owners_pets(
    db_session: Session, service: PetService
) -> None:
    owner_a = _make_user(db_session, email="a@example.com")
    owner_b = _make_user(db_session, email="b@example.com")
    service.create(owner_a.id, _pet_create(name="A1"))
    service.create(owner_a.id, _pet_create(name="A2"))
    service.create(owner_b.id, _pet_create(name="B1"))

    pets_a = service.list_for_owner(owner_a.id)

    assert {pet.name for pet in pets_a} == {"A1", "A2"}
    assert all(pet.owner_id == owner_a.id for pet in pets_a)


def test_list_for_owner_is_empty_for_owner_with_no_pets(service: PetService) -> None:
    assert not service.list_for_owner(uuid4())


# --------------------------------------------------------------------------- #
# update
# --------------------------------------------------------------------------- #


def test_update_changes_supplied_fields(db_session: Session, service: PetService) -> None:
    owner = _make_user(db_session)
    pet = service.create(owner.id, _pet_create(name="Max", species="dog"))

    updated = service.update(pet.id, owner.id, PetUpdate(name="Rex", species="cat"))

    assert updated.name == "Rex"
    assert updated.species == "cat"

    db_session.expire_all()
    reloaded = PetRepository(db_session).get_by_id(pet.id)
    assert reloaded is not None
    assert reloaded.name == "Rex"
    assert reloaded.species == "cat"


def test_update_leaves_omitted_fields_unchanged(db_session: Session, service: PetService) -> None:
    owner = _make_user(db_session)
    pet = service.create(
        owner.id, _pet_create(name="Max", breed="Labrador", weight=Decimal("28.50"))
    )

    service.update(pet.id, owner.id, PetUpdate(name="Rex"))

    db_session.expire_all()
    reloaded = PetRepository(db_session).get_by_id(pet.id)
    assert reloaded is not None
    assert reloaded.name == "Rex"
    assert reloaded.breed == "Labrador"
    assert reloaded.weight == Decimal("28.50")


def test_update_clears_nullable_fields_with_explicit_null(
    db_session: Session, service: PetService
) -> None:
    owner = _make_user(db_session)
    pet = service.create(
        owner.id,
        _pet_create(
            breed="Labrador",
            date_of_birth=date(2022, 5, 12),
            weight=Decimal("28.50"),
            description="Friendly.",
        ),
    )

    service.update(pet.id, owner.id, PetUpdate(breed=None, weight=None))

    db_session.expire_all()
    reloaded = PetRepository(db_session).get_by_id(pet.id)
    assert reloaded is not None
    assert reloaded.breed is None
    assert reloaded.weight is None
    # untouched nullable fields are preserved
    assert reloaded.date_of_birth == date(2022, 5, 12)
    assert reloaded.description == "Friendly."


def test_empty_update_is_a_noop(db_session: Session, service: PetService) -> None:
    owner = _make_user(db_session)
    pet = service.create(owner.id, _pet_create(name="Max", breed="Labrador"))
    original_created_at = pet.created_at

    updated = service.update(pet.id, owner.id, PetUpdate())

    assert updated.id == pet.id
    assert updated.name == "Max"
    assert updated.breed == "Labrador"
    assert updated.created_at == original_created_at


def test_update_does_not_change_id_or_owner_id(db_session: Session, service: PetService) -> None:
    owner = _make_user(db_session)
    pet = service.create(owner.id, _pet_create())
    original_id = pet.id
    original_owner_id = pet.owner_id

    updated = service.update(pet.id, owner.id, PetUpdate(name="Rex"))

    assert updated.id == original_id
    assert updated.owner_id == original_owner_id


def test_update_nonexistent_pet_raises_not_found(db_session: Session, service: PetService) -> None:
    owner = _make_user(db_session)

    with pytest.raises(PetNotFoundError):
        service.update(uuid4(), owner.id, PetUpdate(name="Rex"))


def test_update_other_owners_pet_is_rejected_and_leaves_it_unchanged(
    db_session: Session, service: PetService
) -> None:
    owner_a = _make_user(db_session, email="a@example.com")
    owner_b = _make_user(db_session, email="b@example.com")
    pet = service.create(owner_a.id, _pet_create(name="Max"))

    with pytest.raises(PetNotFoundError):
        service.update(pet.id, owner_b.id, PetUpdate(name="Hacked"))

    db_session.expire_all()
    reloaded = PetRepository(db_session).get_by_id(pet.id)
    assert reloaded is not None
    assert reloaded.name == "Max"


def test_weight_is_preserved_as_decimal_through_create_and_update(
    db_session: Session, service: PetService
) -> None:
    owner = _make_user(db_session)
    pet = service.create(owner.id, _pet_create(weight=Decimal("12.34")))
    assert isinstance(pet.weight, Decimal)

    updated = service.update(pet.id, owner.id, PetUpdate(weight=Decimal("56.78")))

    assert updated.weight == Decimal("56.78")
    assert isinstance(updated.weight, Decimal)
    assert not isinstance(updated.weight, float)

    db_session.expire_all()
    reloaded = PetRepository(db_session).get_by_id(pet.id)
    assert reloaded is not None
    assert reloaded.weight == Decimal("56.78")
    assert isinstance(reloaded.weight, Decimal)


# --------------------------------------------------------------------------- #
# delete
# --------------------------------------------------------------------------- #


def test_delete_removes_the_pet(db_session: Session, service: PetService) -> None:
    owner = _make_user(db_session)
    pet = service.create(owner.id, _pet_create())
    pet_id = pet.id

    service.delete(pet_id, owner.id)

    db_session.expire_all()
    assert PetRepository(db_session).get_by_id(pet_id) is None


def test_delete_is_committed(db_session: Session, service: PetService) -> None:
    owner = _make_user(db_session)
    pet = service.create(owner.id, _pet_create())
    pet_id = pet.id

    service.delete(pet_id, owner.id)
    # The service committed the delete; a rollback must NOT restore it.
    db_session.rollback()

    assert PetRepository(db_session).get_by_id(pet_id) is None


def test_delete_nonexistent_pet_raises_not_found(db_session: Session, service: PetService) -> None:
    owner = _make_user(db_session)

    with pytest.raises(PetNotFoundError):
        service.delete(uuid4(), owner.id)


def test_delete_other_owners_pet_is_rejected_and_leaves_it(
    db_session: Session, service: PetService
) -> None:
    owner_a = _make_user(db_session, email="a@example.com")
    owner_b = _make_user(db_session, email="b@example.com")
    pet = service.create(owner_a.id, _pet_create())

    with pytest.raises(PetNotFoundError):
        service.delete(pet.id, owner_b.id)

    db_session.expire_all()
    assert PetRepository(db_session).get_by_id(pet.id) is not None


def test_get_after_delete_raises_not_found(db_session: Session, service: PetService) -> None:
    owner = _make_user(db_session)
    pet = service.create(owner.id, _pet_create())

    service.delete(pet.id, owner.id)

    with pytest.raises(PetNotFoundError):
        service.get(pet.id, owner.id)


# --------------------------------------------------------------------------- #
# test isolation
# --------------------------------------------------------------------------- #


def test_isolation_between_tests_part_1(db_session: Session, service: PetService) -> None:
    owner = _make_user(db_session, email="iso@example.com")
    service.create(owner.id, _pet_create(name="iso-pet"))

    assert len(service.list_for_owner(owner.id)) == 1


def test_isolation_between_tests_part_2(db_session: Session, service: PetService) -> None:
    # Re-uses the same owner email; a unique-constraint error here would mean
    # part 1's row leaked.
    owner = _make_user(db_session, email="iso@example.com")
    assert not service.list_for_owner(owner.id)

    service.create(owner.id, _pet_create(name="iso-pet"))

    assert len(service.list_for_owner(owner.id)) == 1
