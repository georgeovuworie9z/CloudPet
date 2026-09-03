"""FastAPI dependency providers for the API layer.

``get_current_user`` (the JWT-authenticated user) will be added to this module
in a later step; it belongs next to ``get_user_service``.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.services.user import UserService

SessionDep = Annotated[Session, Depends(get_db)]


def get_user_service(session: SessionDep) -> UserService:
    """A :class:`UserService` bound to the request-scoped database session."""
    return UserService(session)


UserServiceDep = Annotated[UserService, Depends(get_user_service)]
