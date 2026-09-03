"""Pet request/response schemas.

These models validate the *shape* of pet payloads and serialise the ``Pet`` ORM
object. Persistence, ownership, and business rules live in the repository /
service / route layers added in later steps.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Annotated, Literal
from uuid import UUID

from pydantic import (
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    field_validator,
)

from app.schemas.fields import NameStr

PetSex = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=20),
]
"""A pet's sex: trimmed, non-empty, at most 20 characters. An allowed-value set
is intentionally not enforced yet."""

PetDescription = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=1000),
]
"""Free-text description: trimmed, non-empty, at most 1000 characters."""

PetSpecies = Literal[
    "dog",
    "cat",
    "bird",
    "rabbit",
    "hamster",
    "guinea_pig",
    "reptile",
    "other",
]
"""The allowed ``species`` values. Enforced in the schema layer only -- there is
no database constraint."""

PetWeight = Annotated[
    Decimal,
    Field(
        gt=0,
        lt=Decimal("10000"),
        max_digits=6,
        decimal_places=2,
    ),
]
"""A weight compatible with PostgreSQL ``NUMERIC(6, 2)``: greater than 0, less
than 10000, at most 6 significant digits and 2 decimal places. Kept as ``Decimal``."""


class PetCreate(BaseModel):
    """Payload for creating a pet. Unknown fields are rejected.

    The authenticated owner is assigned by the route, never sent by the client,
    so ``owner_id`` is intentionally absent.
    """

    model_config = ConfigDict(extra="forbid")

    name: NameStr
    species: PetSpecies
    breed: NameStr | None = None
    sex: PetSex
    date_of_birth: date | None = None
    weight: PetWeight | None = None
    description: PetDescription | None = None


class PetUpdate(BaseModel):
    """Partial update of a pet. Every field is optional; unknown fields are rejected.

    ``breed``, ``date_of_birth``, ``weight`` and ``description`` may be set to an
    explicit ``null`` to clear them. ``name``, ``species`` and ``sex`` may be
    omitted but must not be ``null``. Use ``model_dump(exclude_unset=True)`` to
    tell an omitted field from one that was explicitly supplied.
    """

    model_config = ConfigDict(extra="forbid")

    name: NameStr | None = None
    species: PetSpecies | None = None
    breed: NameStr | None = None
    sex: PetSex | None = None
    date_of_birth: date | None = None
    weight: PetWeight | None = None
    description: PetDescription | None = None

    @field_validator("name", "species", "sex", mode="before")
    @classmethod
    def _reject_explicit_null(cls, value: object) -> object:
        if value is None:
            raise ValueError("field may not be null")
        return value


class PetResponse(BaseModel):
    """Public representation of a pet, built from the ``Pet`` ORM model."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    owner_id: UUID
    name: str
    species: str
    breed: str | None
    sex: str
    date_of_birth: date | None
    weight: Decimal | None
    description: str | None
    created_at: AwareDatetime
    updated_at: AwareDatetime
