"""Authentication endpoints.

These handlers only translate HTTP <-> :class:`~app.services.user.UserService`
calls. Service exceptions become the standard error envelope via the handlers
registered in :mod:`app.api.errors`.
"""

from __future__ import annotations

from fastapi import APIRouter, status

from app.api.deps import CurrentUserDep, UserServiceDep
from app.api.errors import ErrorResponse
from app.core.jwt import create_access_token
from app.models.user import User
from app.schemas.auth import LoginRequest, TokenResponse, UserCreate
from app.schemas.user import UserResponse

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post(
    "/register",
    status_code=status.HTTP_201_CREATED,
    response_model=UserResponse,
    responses={
        status.HTTP_409_CONFLICT: {"model": ErrorResponse},
        status.HTTP_422_UNPROCESSABLE_CONTENT: {"model": ErrorResponse},
    },
)
def register(payload: UserCreate, service: UserServiceDep) -> User:
    """Create a new account and return its public representation."""
    return service.register(payload)


@router.post(
    "/login",
    response_model=TokenResponse,
    responses={
        status.HTTP_401_UNAUTHORIZED: {"model": ErrorResponse},
        status.HTTP_422_UNPROCESSABLE_CONTENT: {"model": ErrorResponse},
    },
)
def login(payload: LoginRequest, service: UserServiceDep) -> TokenResponse:
    """Verify credentials and return a signed HS256 access token."""
    user = service.authenticate(payload)
    return TokenResponse(access_token=create_access_token(str(user.id)))


@router.get(
    "/me",
    response_model=UserResponse,
    responses={status.HTTP_401_UNAUTHORIZED: {"model": ErrorResponse}},
)
def read_current_user(user: CurrentUserDep) -> User:
    """Return the authenticated user's public representation."""
    return user
