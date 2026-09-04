"""FastAPI dependency providers for the API layer."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.api.errors import NotAuthenticatedError
from app.core.jwt import InvalidTokenError, decode_access_token
from app.db.session import get_db
from app.models.user import User
from app.repositories.user import UserRepository
from app.services.pet import PetService
from app.services.user import UserService

SessionDep = Annotated[Session, Depends(get_db)]

_bearer_scheme = HTTPBearer(auto_error=False)


def get_user_service(session: SessionDep) -> UserService:
    """A :class:`UserService` bound to the request-scoped database session."""
    return UserService(session)


UserServiceDep = Annotated[UserService, Depends(get_user_service)]


def get_pet_service(session: SessionDep) -> PetService:
    """A :class:`PetService` bound to the request-scoped database session."""
    return PetService(session)


PetServiceDep = Annotated[PetService, Depends(get_pet_service)]


def get_user_repository(session: SessionDep) -> UserRepository:
    """A :class:`UserRepository` bound to the request-scoped database session."""
    return UserRepository(session)


def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer_scheme)],
    repository: Annotated[UserRepository, Depends(get_user_repository)],
) -> User:
    """Resolve the authenticated, active user from a ``Bearer`` access token.

    Raises :class:`~app.api.errors.NotAuthenticatedError` (standardised 401) for a
    missing/non-Bearer header, an invalid/expired/wrong-type token, a subject that
    is not a UUID, or a user that does not exist or is inactive -- without
    distinguishing the cases.
    """
    if credentials is None:
        raise NotAuthenticatedError()

    try:
        payload = decode_access_token(credentials.credentials)
    except InvalidTokenError as exc:
        raise NotAuthenticatedError() from exc

    try:
        user_id = UUID(payload.sub)
    except ValueError as exc:
        raise NotAuthenticatedError() from exc

    user = repository.get_by_id(user_id)
    if user is None or not user.is_active:
        raise NotAuthenticatedError()

    return user


CurrentUserDep = Annotated[User, Depends(get_current_user)]
