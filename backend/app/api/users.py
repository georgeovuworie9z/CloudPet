"""Current-user profile endpoints (``/api/v1/users/me``).

Thin handlers: authentication is enforced by ``CurrentUserDep`` and every
mutation delegates to :class:`~app.services.user.UserService`. There is no path
parameter, so a caller can only ever read or change their own profile.
"""

from __future__ import annotations

from fastapi import APIRouter, status

from app.api.deps import CurrentUserDep, UserServiceDep
from app.api.errors import ErrorResponse
from app.models.user import User
from app.schemas.user import UserResponse, UserUpdate

router = APIRouter(prefix="/users", tags=["users"])


@router.get(
    "/me",
    response_model=UserResponse,
    responses={status.HTTP_401_UNAUTHORIZED: {"model": ErrorResponse}},
)
def read_current_user(user: CurrentUserDep) -> User:
    """Return the authenticated user's public representation."""
    return user


@router.put(
    "/me",
    response_model=UserResponse,
    responses={
        status.HTTP_401_UNAUTHORIZED: {"model": ErrorResponse},
        status.HTTP_422_UNPROCESSABLE_CONTENT: {"model": ErrorResponse},
    },
)
def update_current_user(payload: UserUpdate, user: CurrentUserDep, service: UserServiceDep) -> User:
    """Apply a partial update to the authenticated user's profile.

    Only ``first_name``, ``last_name`` and ``phone`` may change. Omitted fields
    are left untouched and an empty body is a valid no-op (no database write).
    An explicit ``null`` for ``first_name`` or ``last_name`` is rejected with
    422 ``INVALID_PROFILE_UPDATE``; ``phone`` may be set to ``null`` to clear it.
    """
    return service.update_profile(user.id, payload)


@router.delete(
    "/me",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={status.HTTP_401_UNAUTHORIZED: {"model": ErrorResponse}},
)
def delete_current_user(user: CurrentUserDep, service: UserServiceDep) -> None:
    """Soft-delete the authenticated user's account.

    Sets ``is_active = False`` and returns ``204`` with no body. The database
    row is retained -- it is not deleted and nothing cascades (there are no
    owned records yet; pets arrive in a later milestone). After this call the
    access token no longer authenticates (``get_current_user`` rejects inactive
    users) and ``POST /api/v1/auth/login`` fails, so the action is effectively
    final from the client's perspective and cannot be repeated with the same
    token.
    """
    service.deactivate(user.id)
