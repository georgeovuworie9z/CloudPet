"""Pet business logic: create, read, list, update, delete -- all owner-scoped.

The service owns persistence transactions (``commit`` / ``rollback`` /
``refresh``); the repository only flushes. Ownership is enforced here, not in
the repository: :meth:`PetService.get` is the single gate reused by
:meth:`update` and :meth:`delete`, and a missing pet and a pet owned by someone
else raise the same :class:`PetNotFoundError`.
"""

from __future__ import annotations

from collections.abc import Sequence
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.pet import Pet
from app.repositories.pet import PetRepository
from app.schemas.pet import PetCreate, PetUpdate
from app.services.exceptions import PetNotFoundError

_MUTABLE_PET_FIELDS = ("name", "species", "breed", "sex", "date_of_birth", "weight", "description")


class PetService:
    """Owner-scoped operations on pets, bound to a single :class:`Session`."""

    def __init__(self, session: Session, repository: PetRepository | None = None) -> None:
        self._session = session
        self._pets = repository if repository is not None else PetRepository(session)

    def create(self, owner_id: UUID, data: PetCreate) -> Pet:
        """Create and persist a pet owned by ``owner_id``.

        The owner is always the authenticated caller passed in here; ``data``
        cannot carry an ``owner_id``.
        """
        pet = Pet(
            owner_id=owner_id,
            name=data.name,
            species=data.species,
            breed=data.breed,
            sex=data.sex,
            date_of_birth=data.date_of_birth,
            weight=data.weight,
            description=data.description,
        )
        self._pets.create(pet)
        self._session.commit()
        self._session.refresh(pet)
        return pet

    def get(self, pet_id: UUID, owner_id: UUID) -> Pet:
        """Return ``owner_id``'s pet with ``pet_id``.

        Raises :class:`PetNotFoundError` if no such pet exists *or* it belongs to
        another user -- the two cases are indistinguishable.
        """
        pet = self._pets.get_by_id(pet_id)
        if pet is None or pet.owner_id != owner_id:
            raise PetNotFoundError(str(pet_id))
        return pet

    def list_for_owner(self, owner_id: UUID) -> Sequence[Pet]:
        """Return every pet owned by ``owner_id`` (ordered by ``created_at``)."""
        return self._pets.list_by_owner(owner_id)

    def update(self, pet_id: UUID, owner_id: UUID, data: PetUpdate) -> Pet:
        """Apply a partial update to ``owner_id``'s pet ``pet_id``.

        Only fields explicitly supplied in ``data`` change; an explicit ``null``
        clears a nullable field. ``name`` / ``species`` / ``sex`` can never be
        ``null`` (the schema rejects it). ``id``, ``owner_id`` and the
        timestamps are never modified here. An empty payload is a no-op.
        """
        pet = self.get(pet_id, owner_id)

        supplied = data.model_dump(exclude_unset=True)
        changed = False
        for field in _MUTABLE_PET_FIELDS:
            if field in supplied:
                setattr(pet, field, supplied[field])
                changed = True

        if changed:
            self._pets.save(pet)
            self._session.commit()
            self._session.refresh(pet)
        return pet

    def delete(self, pet_id: UUID, owner_id: UUID) -> None:
        """Permanently delete ``owner_id``'s pet ``pet_id`` (a hard delete)."""
        pet = self.get(pet_id, owner_id)
        self._pets.delete(pet)
        self._session.commit()
