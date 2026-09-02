"""User resource schemas."""

from __future__ import annotations

from uuid import UUID

from pydantic import AwareDatetime, BaseModel, ConfigDict

from app.schemas.fields import NameStr, PhoneStr


class UserResponse(BaseModel):
    """Public representation of a user.

    Built from the ``User`` ORM model via ``model_validate`` (``from_attributes``).
    ``password_hash`` is not a field here and is therefore never serialised.
    """

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    email: str
    first_name: str
    last_name: str
    phone: str | None
    is_active: bool
    created_at: AwareDatetime
    updated_at: AwareDatetime


class UserUpdate(BaseModel):
    """Partial update of the caller's own mutable profile fields.

    Every field is optional; an empty payload is a valid no-op. Unknown fields
    are rejected, so ``email``, ``id``, ``is_active``, ``password``,
    ``password_hash`` and the timestamps cannot be set through this schema.

    Use ``model_dump(exclude_unset=True)`` to distinguish an omitted field from
    one explicitly supplied (including an explicit ``null``).
    """

    model_config = ConfigDict(extra="forbid")

    first_name: NameStr | None = None
    last_name: NameStr | None = None
    phone: PhoneStr | None = None
