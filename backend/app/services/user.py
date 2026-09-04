"""User business logic: registration, authentication, profile updates, deactivation.

The service owns persistence transactions (``commit`` / ``rollback``); the
repository only flushes. JWT creation and HTTP concerns are deliberately absent
-- they belong to the route layer added in a later step.
"""

from __future__ import annotations

import logging
from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.security import hash_password, verify_password
from app.models.user import User
from app.repositories.user import UserRepository
from app.schemas.auth import LoginRequest, UserCreate
from app.schemas.user import UserUpdate
from app.services.exceptions import (
    DuplicateEmailError,
    InvalidCredentialsError,
    InvalidProfileUpdateError,
    UserNotFoundError,
)

logger = logging.getLogger(__name__)

_MUTABLE_PROFILE_FIELDS = ("first_name", "last_name", "phone")
_REQUIRED_PROFILE_FIELDS = ("first_name", "last_name")


class UserService:
    """Business operations on users, scoped to a single :class:`Session`."""

    def __init__(self, session: Session, repository: UserRepository | None = None) -> None:
        self._session = session
        self._users = repository if repository is not None else UserRepository(session)

    def register(self, data: UserCreate) -> User:
        """Create and persist a new user from validated registration input.

        ``data.email`` is already normalised by the schema. Raises
        :class:`DuplicateEmailError` if the email is taken. The password is
        stored only as an Argon2id hash; the plaintext is never persisted.
        """
        if self._users.get_by_email(data.email) is not None:
            raise DuplicateEmailError("email already registered")

        user = User(
            email=data.email,
            password_hash=hash_password(data.password),
            first_name=data.first_name,
            last_name=data.last_name,
            phone=data.phone,
        )
        self._users.create(user)
        try:
            self._session.commit()
        except IntegrityError as exc:
            # Lost a race on the unique email constraint.
            self._session.rollback()
            raise DuplicateEmailError("email already registered") from exc

        self._session.refresh(user)
        return user

    def authenticate(self, credentials: LoginRequest) -> User:
        """Return the user for valid credentials, else raise :class:`InvalidCredentialsError`.

        The same exception is raised for an unknown email, a wrong password, and
        an inactive account, so callers cannot distinguish the cases. For the
        same reason, a failed attempt is logged with no identifying information
        at all (no email, no reason) -- the log must not become an oracle any
        more than the exception is.
        """
        user = self._users.get_by_email(credentials.email)
        if user is None or not user.is_active:
            logger.warning("Authentication failed")
            raise InvalidCredentialsError("invalid email or password")
        if not verify_password(credentials.password, user.password_hash):
            logger.warning("Authentication failed")
            raise InvalidCredentialsError("invalid email or password")
        logger.info("Authentication succeeded", extra={"user_id": str(user.id)})
        return user

    def update_profile(self, user_id: UUID, data: UserUpdate) -> User:
        """Apply a partial profile update to the user identified by ``user_id``.

        Only ``first_name``, ``last_name`` and ``phone`` can change, and only
        when supplied by the caller. An explicit ``null`` for ``first_name`` or
        ``last_name`` (both ``NOT NULL`` columns) raises
        :class:`InvalidProfileUpdateError` rather than reaching the database.
        Email, password, ``is_active``, id and timestamps are never touched here.
        """
        user = self._get_or_raise(user_id)

        supplied = data.model_dump(exclude_unset=True)
        for field in _REQUIRED_PROFILE_FIELDS:
            if field in supplied and supplied[field] is None:
                raise InvalidProfileUpdateError(f"{field} may not be null")

        changed = False
        for field in _MUTABLE_PROFILE_FIELDS:
            if field in supplied:
                setattr(user, field, supplied[field])
                changed = True

        if changed:
            self._users.save(user)
            self._session.commit()
            self._session.refresh(user)
        return user

    def deactivate(self, user_id: UUID) -> User:
        """Soft-delete the user identified by ``user_id`` (``is_active = False``).

        The row is kept. Calling this on an already-inactive user is a no-op:
        it returns the user unchanged without touching the database.
        """
        user = self._get_or_raise(user_id)
        if user.is_active:
            self._users.deactivate(user)
            self._session.commit()
            self._session.refresh(user)
        return user

    def _get_or_raise(self, user_id: UUID) -> User:
        user = self._users.get_by_id(user_id)
        if user is None:
            raise UserNotFoundError(str(user_id))
        return user
