"""Unit tests for the pet resource schemas (no database)."""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from app.models.pet import Pet
from app.schemas.pet import PetCreate, PetResponse, PetUpdate
from pydantic import ValidationError

ALLOWED_SPECIES = (
    "dog",
    "cat",
    "bird",
    "rabbit",
    "hamster",
    "guinea_pig",
    "reptile",
    "other",
)


def _create_kwargs(**overrides: object) -> dict[str, object]:
    base: dict[str, object] = {"name": "Max", "species": "dog", "sex": "male"}
    base.update(overrides)
    return base


def _make_pet(**overrides: object) -> Pet:
    """An in-memory ``Pet`` ORM instance (never added to a session)."""
    defaults: dict[str, object] = {
        "id": uuid4(),
        "owner_id": uuid4(),
        "name": "Max",
        "species": "dog",
        "breed": None,
        "sex": "male",
        "date_of_birth": None,
        "weight": None,
        "description": None,
        "created_at": datetime(2026, 9, 1, 12, 0, tzinfo=UTC),
        "updated_at": datetime(2026, 9, 2, 12, 0, tzinfo=UTC),
    }
    defaults.update(overrides)
    return Pet(**defaults)


class TestPetCreate:
    def test_valid_pet_create_with_all_fields(self) -> None:
        pet = PetCreate(
            name="Max",
            species="dog",
            breed="Labrador",
            sex="male",
            date_of_birth=date(2022, 5, 12),
            weight=Decimal("28.50"),
            description="Friendly and energetic.",
        )

        assert pet.name == "Max"
        assert pet.species == "dog"
        assert pet.breed == "Labrador"
        assert pet.sex == "male"
        assert pet.date_of_birth == date(2022, 5, 12)
        assert pet.weight == Decimal("28.50")
        assert isinstance(pet.weight, Decimal)
        assert pet.description == "Friendly and energetic."

    def test_minimal_valid_pet_create(self) -> None:
        pet = PetCreate(**_create_kwargs())

        assert pet.name == "Max"
        assert pet.breed is None
        assert pet.date_of_birth is None
        assert pet.weight is None
        assert pet.description is None

    @pytest.mark.parametrize("missing", ["name", "species", "sex"])
    def test_required_field_missing_is_rejected(self, missing: str) -> None:
        kwargs = _create_kwargs()
        del kwargs[missing]

        with pytest.raises(ValidationError):
            PetCreate(**kwargs)

    def test_name_over_100_chars_is_rejected(self) -> None:
        with pytest.raises(ValidationError):
            PetCreate(**_create_kwargs(name="x" * 101))

    def test_name_at_100_chars_is_accepted(self) -> None:
        pet = PetCreate(**_create_kwargs(name="x" * 100))
        assert pet.name == "x" * 100

    def test_name_is_trimmed(self) -> None:
        pet = PetCreate(**_create_kwargs(name="  Max  "))
        assert pet.name == "Max"

    def test_species_over_50_chars_is_rejected(self) -> None:
        with pytest.raises(ValidationError):
            PetCreate(**_create_kwargs(species="x" * 51))

    def test_invalid_species_is_rejected(self) -> None:
        with pytest.raises(ValidationError):
            PetCreate(**_create_kwargs(species="dinosaur"))

    @pytest.mark.parametrize("species", ALLOWED_SPECIES)
    def test_each_allowed_species_is_accepted(self, species: str) -> None:
        pet = PetCreate(**_create_kwargs(species=species))
        assert pet.species == species

    def test_breed_over_100_chars_is_rejected(self) -> None:
        with pytest.raises(ValidationError):
            PetCreate(**_create_kwargs(breed="x" * 101))

    def test_sex_is_required(self) -> None:
        kwargs = _create_kwargs()
        del kwargs["sex"]
        with pytest.raises(ValidationError):
            PetCreate(**kwargs)

    def test_sex_null_is_rejected(self) -> None:
        with pytest.raises(ValidationError):
            PetCreate(**_create_kwargs(sex=None))

    def test_sex_over_20_chars_is_rejected(self) -> None:
        with pytest.raises(ValidationError):
            PetCreate(**_create_kwargs(sex="x" * 21))

    def test_date_of_birth_accepts_a_date(self) -> None:
        pet = PetCreate(**_create_kwargs(date_of_birth=date(2020, 1, 1)))
        assert pet.date_of_birth == date(2020, 1, 1)

    def test_weight_is_kept_as_decimal(self) -> None:
        pet = PetCreate(**_create_kwargs(weight=Decimal("12.34")))
        assert pet.weight == Decimal("12.34")
        assert isinstance(pet.weight, Decimal)
        assert not isinstance(pet.weight, float)

    @pytest.mark.parametrize(
        "weight",
        [
            Decimal("28.555"),  # 3 decimal places -> exceeds scale
            Decimal("10000.00"),  # too large for NUMERIC(6, 2)
            Decimal("99999.9"),  # 6 digits, but integer part too big at scale 2
            Decimal("0"),  # not > 0
            Decimal("-5.00"),  # not > 0
        ],
    )
    def test_weight_outside_numeric_6_2_is_rejected(self, weight: Decimal) -> None:
        with pytest.raises(ValidationError):
            PetCreate(**_create_kwargs(weight=weight))

    @pytest.mark.parametrize("weight", [Decimal("9999.99"), Decimal("28.5"), Decimal("28")])
    def test_weight_within_numeric_6_2_is_accepted(self, weight: Decimal) -> None:
        pet = PetCreate(**_create_kwargs(weight=weight))
        assert pet.weight == weight

    def test_description_over_1000_chars_is_rejected(self) -> None:
        with pytest.raises(ValidationError):
            PetCreate(**_create_kwargs(description="x" * 1001))

    def test_description_at_1000_chars_is_accepted(self) -> None:
        pet = PetCreate(**_create_kwargs(description="x" * 1000))
        assert pet.description == "x" * 1000

    def test_nullable_fields_accept_none(self) -> None:
        pet = PetCreate(
            **_create_kwargs(breed=None, date_of_birth=None, weight=None, description=None)
        )
        assert pet.breed is None
        assert pet.date_of_birth is None
        assert pet.weight is None
        assert pet.description is None

    def test_unexpected_field_is_rejected(self) -> None:
        with pytest.raises(ValidationError):
            PetCreate.model_validate(_create_kwargs(owner_id=str(uuid4())))


class TestPetUpdate:
    def test_empty_update_dumps_to_nothing(self) -> None:
        assert PetUpdate().model_dump(exclude_unset=True) == {}

    def test_supplied_field_is_in_the_dump(self) -> None:
        assert PetUpdate(name="Rex").model_dump(exclude_unset=True) == {"name": "Rex"}

    def test_omitted_is_distinct_from_explicit_null_on_nullable_fields(self) -> None:
        assert PetUpdate().model_dump(exclude_unset=True) == {}
        assert PetUpdate(breed=None).model_dump(exclude_unset=True) == {"breed": None}
        assert PetUpdate(weight=None).model_dump(exclude_unset=True) == {"weight": None}
        assert PetUpdate(date_of_birth=None).model_dump(exclude_unset=True) == {
            "date_of_birth": None
        }
        assert PetUpdate(description=None).model_dump(exclude_unset=True) == {"description": None}

    @pytest.mark.parametrize("field", ["name", "species", "sex"])
    def test_explicit_null_for_non_nullable_field_is_rejected(self, field: str) -> None:
        with pytest.raises(ValidationError):
            PetUpdate.model_validate({field: None})

    def test_nullable_fields_accept_explicit_null(self) -> None:
        update = PetUpdate(breed=None, date_of_birth=None, weight=None, description=None)
        assert update.breed is None
        assert update.date_of_birth is None
        assert update.weight is None
        assert update.description is None

    def test_species_uses_the_same_allowed_values(self) -> None:
        assert PetUpdate(species="cat").species == "cat"
        with pytest.raises(ValidationError):
            PetUpdate(species="dinosaur")
        with pytest.raises(ValidationError):
            PetUpdate(species="x" * 51)

    def test_max_lengths_are_still_enforced(self) -> None:
        with pytest.raises(ValidationError):
            PetUpdate(name="x" * 101)
        with pytest.raises(ValidationError):
            PetUpdate(breed="x" * 101)
        with pytest.raises(ValidationError):
            PetUpdate(sex="x" * 21)
        with pytest.raises(ValidationError):
            PetUpdate(description="x" * 1001)

    def test_weight_precision_rules_still_apply(self) -> None:
        assert PetUpdate(weight=Decimal("28.50")).weight == Decimal("28.50")
        with pytest.raises(ValidationError):
            PetUpdate(weight=Decimal("28.555"))
        with pytest.raises(ValidationError):
            PetUpdate(weight=Decimal("10000.00"))

    def test_unexpected_field_is_rejected(self) -> None:
        with pytest.raises(ValidationError):
            PetUpdate.model_validate({"owner_id": str(uuid4())})


class TestPetResponse:
    def test_serialises_from_the_orm_model(self) -> None:
        pet = _make_pet(
            breed="Labrador",
            date_of_birth=date(2022, 5, 12),
            weight=Decimal("28.50"),
            description="Friendly.",
        )

        response = PetResponse.model_validate(pet)

        assert response.id == pet.id
        assert isinstance(response.id, UUID)
        assert response.owner_id == pet.owner_id
        assert isinstance(response.owner_id, UUID)
        assert response.name == "Max"
        assert response.species == "dog"
        assert response.breed == "Labrador"
        assert response.sex == "male"
        assert response.date_of_birth == date(2022, 5, 12)
        assert response.weight == Decimal("28.50")
        assert response.description == "Friendly."
        assert response.created_at.tzinfo is not None
        assert response.updated_at.tzinfo is not None

    def test_nullable_fields_serialise_as_none(self) -> None:
        response = PetResponse.model_validate(_make_pet())

        assert response.breed is None
        assert response.date_of_birth is None
        assert response.weight is None
        assert response.description is None

    def test_weight_is_preserved_as_decimal_not_float(self) -> None:
        response = PetResponse.model_validate(_make_pet(weight=Decimal("28.50")))

        assert isinstance(response.weight, Decimal)
        assert not isinstance(response.weight, float)
        assert response.model_dump()["weight"] == Decimal("28.50")
        assert isinstance(response.model_dump()["weight"], Decimal)

    def test_naive_timestamps_are_rejected(self) -> None:
        with pytest.raises(ValidationError):
            PetResponse.model_validate(_make_pet(created_at=datetime(2026, 1, 1, 12, 0)))
