"""DB-backed tests for the :class:`~app.models.pet.Pet` ORM model and its migration.

Run against the real PostgreSQL test database via the ``db_session`` fixture
(one transaction per test, rolled back afterwards).
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import UUID, uuid4

import pytest
import sqlalchemy as sa
from app.models.pet import Pet
from app.models.user import User
from sqlalchemy import inspect
from sqlalchemy.exc import DataError, IntegrityError
from sqlalchemy.orm import Session
from sqlalchemy.schema import ColumnDefault

_HASH = "$argon2id$v=19$m=65536,t=3,p=4$c2FsdHNhbHRzYWx0$aGFzaGhhc2hoYXNoaGFzaA"
_NOT_NULL_COLUMNS = ("owner_id", "name", "species", "sex")


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


def test_create_and_reload_pet_owned_by_user(db_session: Session) -> None:
    user = _make_user(db_session)
    pet = _make_pet(
        user.id,
        breed="Labrador",
        date_of_birth=date(2022, 5, 12),
        weight=Decimal("28.50"),
        description="Friendly and energetic.",
    )
    db_session.add(pet)
    db_session.commit()
    pet_id = pet.id
    db_session.expire_all()

    reloaded = db_session.get(Pet, pet_id)
    assert reloaded is not None
    assert reloaded.owner_id == user.id
    assert reloaded.name == "Max"
    assert reloaded.species == "dog"
    assert reloaded.sex == "male"
    assert reloaded.breed == "Labrador"
    assert reloaded.date_of_birth == date(2022, 5, 12)
    assert reloaded.weight == Decimal("28.50")
    assert reloaded.description == "Friendly and energetic."


def test_uuid_and_timestamp_behaviour(db_session: Session) -> None:
    user = _make_user(db_session)
    pet = _make_pet(user.id)
    db_session.add(pet)
    db_session.commit()
    db_session.refresh(pet)

    assert isinstance(pet.id, UUID)
    assert pet.id.version == 4
    assert pet.id != user.id
    assert pet.created_at.tzinfo is not None
    assert pet.updated_at.tzinfo is not None


def test_nullable_fields_accept_none(db_session: Session) -> None:
    user = _make_user(db_session)
    pet = _make_pet(user.id)
    db_session.add(pet)
    db_session.commit()
    db_session.refresh(pet)

    assert pet.breed is None
    assert pet.date_of_birth is None
    assert pet.weight is None
    assert pet.description is None


@pytest.mark.parametrize("missing", _NOT_NULL_COLUMNS)
def test_not_null_columns_are_enforced(db_session: Session, missing: str) -> None:
    user = _make_user(db_session)
    kwargs: dict[str, object] = {
        "owner_id": user.id,
        "name": "Max",
        "species": "dog",
        "sex": "male",
    }
    del kwargs[missing]

    db_session.add(Pet(**kwargs))
    with pytest.raises(IntegrityError):
        db_session.flush()
    db_session.rollback()


def test_foreign_key_requires_an_existing_owner(db_session: Session) -> None:
    db_session.add(_make_pet(uuid4()))
    with pytest.raises(IntegrityError):
        db_session.flush()
    db_session.rollback()


def test_weight_numeric_6_2_round_trips_and_rounds(db_session: Session) -> None:
    user = _make_user(db_session)

    exact = _make_pet(user.id, weight=Decimal("28.55"))
    db_session.add(exact)
    db_session.commit()
    db_session.refresh(exact)
    assert exact.weight == Decimal("28.55")

    rounded = _make_pet(user.id, name="Rounder", weight=Decimal("28.555"))
    db_session.add(rounded)
    db_session.commit()
    db_session.refresh(rounded)
    assert rounded.weight == Decimal("28.56")


def test_weight_overflowing_numeric_6_2_is_rejected(db_session: Session) -> None:
    user = _make_user(db_session)
    db_session.add(_make_pet(user.id, weight=Decimal("10000.00")))
    with pytest.raises(DataError):
        db_session.flush()
    db_session.rollback()


def test_date_of_birth_round_trips_as_a_date(db_session: Session) -> None:
    user = _make_user(db_session)
    pet = _make_pet(user.id, date_of_birth=date(2022, 5, 12))
    db_session.add(pet)
    db_session.commit()
    db_session.refresh(pet)

    assert pet.date_of_birth == date(2022, 5, 12)
    assert type(pet.date_of_birth) is date


def test_model_and_migration_are_in_parity(db_session: Session) -> None:
    inspector = inspect(db_session.connection())

    db_columns = {col["name"]: col for col in inspector.get_columns("pets")}
    model_columns = Pet.__table__.columns

    # column set matches the model
    assert set(db_columns) == set(model_columns.keys())

    # nullability matches the model, column by column
    for name, model_col in model_columns.items():
        assert db_columns[name]["nullable"] == model_col.nullable, name

    # column types
    assert str(db_columns["id"]["type"]) == "UUID"
    assert str(db_columns["owner_id"]["type"]) == "UUID"
    assert str(db_columns["name"]["type"]) == "VARCHAR(100)"
    assert str(db_columns["species"]["type"]) == "VARCHAR(50)"
    assert str(db_columns["breed"]["type"]) == "VARCHAR(100)"
    assert str(db_columns["sex"]["type"]) == "VARCHAR(20)"
    assert str(db_columns["date_of_birth"]["type"]) == "DATE"
    assert str(db_columns["weight"]["type"]) == "NUMERIC(6, 2)"
    assert str(db_columns["description"]["type"]) == "VARCHAR(1000)"
    for stamp in ("created_at", "updated_at"):
        stamp_type = db_columns[stamp]["type"]
        assert isinstance(stamp_type, sa.DateTime)
        assert stamp_type.timezone is True
        assert db_columns[stamp]["default"] is not None  # server_default now()

    # primary key
    assert inspector.get_pk_constraint("pets")["constrained_columns"] == ["id"]

    # foreign key -- name + mapping (from the migrated DB)
    foreign_keys = inspector.get_foreign_keys("pets")
    assert len(foreign_keys) == 1
    fk = foreign_keys[0]
    assert fk["name"] == "fk_pets_owner_id_users"
    assert fk["constrained_columns"] == ["owner_id"]
    assert fk["referred_table"] == "users"
    assert fk["referred_columns"] == ["id"]

    # foreign key -- name + ON DELETE behaviour (from the model)
    model_fk = next(iter(model_columns["owner_id"].foreign_keys))
    assert model_fk.name == "fk_pets_owner_id_users"
    assert model_fk.ondelete == "NO ACTION"

    # index on owner_id
    indexes = {ix["name"]: ix for ix in inspector.get_indexes("pets")}
    assert "ix_pets_owner_id" in indexes
    assert indexes["ix_pets_owner_id"]["column_names"] == ["owner_id"]

    # updated_at declares a SQL onupdate of now() (harness-safe -- see module docstring)
    onupdate = model_columns["updated_at"].onupdate
    assert isinstance(onupdate, ColumnDefault)
    assert "now" in str(onupdate.arg).lower()
