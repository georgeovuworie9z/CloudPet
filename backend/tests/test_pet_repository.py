"""Repository tests for :class:`~app.repositories.pet.PetRepository`.

Run against the real PostgreSQL test database via the ``db_session`` fixture,
which wraps each test in a transaction that is rolled back afterwards. No mocks.
Follows the patterns established by ``test_user_repository.py``.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
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

    pets_a = repository.list_by_owner(owner_a.id, limit=100, offset=0)

    assert {pet.name for pet in pets_a} == {"A1", "A2"}
    assert all(pet.owner_id == owner_a.id for pet in pets_a)


def test_list_by_owner_is_empty_for_owner_with_no_pets(repository: PetRepository) -> None:
    assert not repository.list_by_owner(uuid4(), limit=100, offset=0)


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

    names = [pet.name for pet in repository.list_by_owner(owner.id, limit=100, offset=0)]

    assert names == ["early", "middle", "late"]


# --------------------------------------------------------------------------- #
# list_by_owner -- pagination
# --------------------------------------------------------------------------- #


def _seed(repository: PetRepository, owner_id: UUID, count: int) -> list[UUID]:
    """Create ``count`` pets with strictly increasing ``created_at``; return ids in order."""
    base = datetime(2024, 1, 1, tzinfo=UTC)
    ids: list[UUID] = []
    for i in range(count):
        pet = repository.create(
            _make_pet(owner_id, name=f"pet-{i:02d}", created_at=base + timedelta(days=i))
        )
        ids.append(pet.id)
    return ids


def test_list_by_owner_limit_caps_the_page_size(
    db_session: Session, repository: PetRepository
) -> None:
    owner = _make_user(db_session)
    _seed(repository, owner.id, 5)
    db_session.commit()

    assert len(repository.list_by_owner(owner.id, limit=2, offset=0)) == 2


def test_list_by_owner_offset_skips_leading_rows(
    db_session: Session, repository: PetRepository
) -> None:
    owner = _make_user(db_session)
    ids = _seed(repository, owner.id, 5)
    db_session.commit()

    page = repository.list_by_owner(owner.id, limit=100, offset=2)

    assert [pet.id for pet in page] == ids[2:]


def test_list_by_owner_limit_and_offset_return_the_expected_slice(
    db_session: Session, repository: PetRepository
) -> None:
    owner = _make_user(db_session)
    ids = _seed(repository, owner.id, 5)
    db_session.commit()

    page = repository.list_by_owner(owner.id, limit=2, offset=1)

    assert [pet.id for pet in page] == ids[1:3]


def test_list_by_owner_pages_do_not_overlap_and_cover_everything(
    db_session: Session, repository: PetRepository
) -> None:
    owner = _make_user(db_session)
    ids = _seed(repository, owner.id, 5)
    db_session.commit()

    collected: list[UUID] = []
    for offset in (0, 2, 4, 6):
        page = repository.list_by_owner(owner.id, limit=2, offset=offset)
        collected.extend(pet.id for pet in page)

    assert collected == ids
    assert len(set(collected)) == len(collected)


def test_list_by_owner_offset_past_the_end_is_empty(
    db_session: Session, repository: PetRepository
) -> None:
    owner = _make_user(db_session)
    _seed(repository, owner.id, 3)
    db_session.commit()

    assert not repository.list_by_owner(owner.id, limit=100, offset=99)


def test_list_by_owner_breaks_created_at_ties_by_id(
    db_session: Session, repository: PetRepository
) -> None:
    owner = _make_user(db_session)
    tie = datetime(2024, 6, 1, tzinfo=UTC)
    for i in range(4):
        repository.create(_make_pet(owner.id, name=f"tie-{i}", created_at=tie))
    db_session.commit()

    full = [pet.id for pet in repository.list_by_owner(owner.id, limit=100, offset=0)]
    again = [pet.id for pet in repository.list_by_owner(owner.id, limit=100, offset=0)]

    assert full == sorted(full)  # ascending by id when created_at ties
    assert full == again  # repeatable across queries

    paged: list[UUID] = []
    for offset in (0, 2, 4):
        page = repository.list_by_owner(owner.id, limit=2, offset=offset)
        paged.extend(pet.id for pet in page)
    assert paged == full


def test_list_by_owner_pagination_is_owner_scoped(
    db_session: Session, repository: PetRepository
) -> None:
    owner_a = _make_user(db_session, email="a@example.com")
    owner_b = _make_user(db_session, email="b@example.com")
    _seed(repository, owner_a.id, 3)
    b_ids = set(_seed(repository, owner_b.id, 3))
    db_session.commit()

    page = repository.list_by_owner(owner_a.id, limit=100, offset=0)

    assert all(pet.owner_id == owner_a.id for pet in page)
    assert not (b_ids & {pet.id for pet in page})


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

    assert len(repository.list_by_owner(owner.id, limit=100, offset=0)) == 1


def test_isolation_between_tests_part_2(db_session: Session, repository: PetRepository) -> None:
    # Re-uses the same owner email; a unique-constraint error here would mean
    # part 1's row leaked.
    owner = _make_user(db_session, email="iso@example.com")
    assert not repository.list_by_owner(owner.id, limit=100, offset=0)

    repository.create(_make_pet(owner.id, name="iso-pet"))
    db_session.commit()

    assert len(repository.list_by_owner(owner.id, limit=100, offset=0)) == 1
