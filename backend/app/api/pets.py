"""Pet CRUD endpoints (``/api/v1/pets``).

Thin handlers: authentication is enforced by ``CurrentUserDep`` and every
operation delegates to :class:`~app.services.pet.PetService`, which is the single
ownership gate. The authenticated user is always the owner -- ``owner_id`` is
never read from request data. A pet that does not exist and a pet owned by
another user both surface as the same 404 ``PET_NOT_FOUND``.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Query, status

from app.api.deps import CurrentUserDep, PetServiceDep
from app.api.errors import ErrorResponse
from app.models.pet import Pet
from app.schemas.pet import PetCreate, PetResponse, PetUpdate

router = APIRouter(prefix="/pets", tags=["pets"])


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    response_model=PetResponse,
    responses={
        status.HTTP_401_UNAUTHORIZED: {"model": ErrorResponse},
        status.HTTP_422_UNPROCESSABLE_CONTENT: {"model": ErrorResponse},
    },
)
def create_pet(payload: PetCreate, user: CurrentUserDep, service: PetServiceDep) -> Pet:
    """Create a pet owned by the authenticated user and return it."""
    return service.create(user.id, payload)


@router.get(
    "",
    response_model=list[PetResponse],
    responses={status.HTTP_401_UNAUTHORIZED: {"model": ErrorResponse}},
)
def list_pets(
    user: CurrentUserDep,
    service: PetServiceDep,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> Sequence[Pet]:
    """Return one page of the authenticated user's pets.

    Ordered by ``created_at`` then ``id``. ``limit`` defaults to 20 (max 100);
    ``offset`` defaults to 0. Paging is applied in SQL -- the full collection is
    never loaded.
    """
    return service.list_for_owner(user.id, limit=limit, offset=offset)


@router.get(
    "/{pet_id}",
    response_model=PetResponse,
    responses={
        status.HTTP_401_UNAUTHORIZED: {"model": ErrorResponse},
        status.HTTP_404_NOT_FOUND: {"model": ErrorResponse},
    },
)
def get_pet(pet_id: UUID, user: CurrentUserDep, service: PetServiceDep) -> Pet:
    """Return the authenticated user's pet with ``pet_id``.

    A pet that does not exist and one owned by another user are indistinguishable:
    both return 404 ``PET_NOT_FOUND``.
    """
    return service.get(pet_id, user.id)


@router.patch(
    "/{pet_id}",
    response_model=PetResponse,
    responses={
        status.HTTP_401_UNAUTHORIZED: {"model": ErrorResponse},
        status.HTTP_404_NOT_FOUND: {"model": ErrorResponse},
        status.HTTP_422_UNPROCESSABLE_CONTENT: {"model": ErrorResponse},
    },
)
def update_pet(
    pet_id: UUID, payload: PetUpdate, user: CurrentUserDep, service: PetServiceDep
) -> Pet:
    """Apply a partial update to the authenticated user's pet ``pet_id``.

    Only supplied fields change; an explicit ``null`` clears a nullable field,
    while ``name`` / ``species`` / ``sex`` reject ``null`` (schema-level 422).
    ``id`` and ``owner_id`` can never be set, and an empty body is a no-op.
    """
    return service.update(pet_id, user.id, payload)


@router.delete(
    "/{pet_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={
        status.HTTP_401_UNAUTHORIZED: {"model": ErrorResponse},
        status.HTTP_404_NOT_FOUND: {"model": ErrorResponse},
    },
)
def delete_pet(pet_id: UUID, user: CurrentUserDep, service: PetServiceDep) -> None:
    """Permanently delete the authenticated user's pet ``pet_id`` (a hard delete)."""
    service.delete(pet_id, user.id)
