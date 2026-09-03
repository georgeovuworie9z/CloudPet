"""Database access for the :class:`~app.models.pet.Pet` aggregate.

This layer only reads and writes rows. It does not enforce ownership, apply
business rules, or validate API input -- those belong to the service layer. It
also does not own transactions: write methods ``flush`` so that SQL is emitted
(and constraint errors surface immediately), but the caller is responsible for
``commit`` / ``rollback``.
"""

from __future__ import annotations

from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.pet import Pet


class PetRepository:
    """CRUD operations for pets, scoped to a single :class:`Session`."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def get_by_id(self, pet_id: UUID) -> Pet | None:
        """Return the pet with ``pet_id``, or ``None`` if there is no such row.

        Ownership is not considered here; callers that need it must check
        ``pet.owner_id`` themselves.
        """
        return self._session.get(Pet, pet_id)

    def list_by_owner(self, owner_id: UUID) -> Sequence[Pet]:
        """Return every pet owned by ``owner_id``, ordered by ``created_at`` ascending."""
        statement = select(Pet).where(Pet.owner_id == owner_id).order_by(Pet.created_at)
        return self._session.scalars(statement).all()

    def create(self, pet: Pet) -> Pet:
        """Add a new ``pet`` to the session and flush the INSERT."""
        self._session.add(pet)
        self._session.flush()
        return pet

    def save(self, pet: Pet) -> Pet:
        """Flush pending changes to an existing ``pet``."""
        self._session.add(pet)
        self._session.flush()
        return pet

    def delete(self, pet: Pet) -> None:
        """Delete ``pet``'s row and flush the DELETE."""
        self._session.delete(pet)
        self._session.flush()
