"""Database access for the :class:`~app.models.user.User` aggregate.

This layer only reads and writes rows. It does not hash passwords, issue
tokens, validate API input, or apply business rules -- those belong to the
service layer. It also does not own transactions: methods ``flush`` so that
SQL is emitted (and constraint errors surface immediately), but the caller is
responsible for ``commit`` / ``rollback``.
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.user import User


class UserRepository:
    """CRUD operations for users, scoped to a single :class:`Session`."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def get_by_id(self, user_id: UUID) -> User | None:
        """Return the user with ``user_id``, or ``None`` if there is no such row."""
        return self._session.get(User, user_id)

    def get_by_email(self, email: str) -> User | None:
        """Return the user whose email equals ``email`` exactly, or ``None``.

        The caller is responsible for passing an already-normalised address;
        the lookup is a plain equality match.
        """
        return self._session.scalars(select(User).where(User.email == email)).one_or_none()

    def create(self, user: User) -> User:
        """Add a new ``user`` to the session and flush the INSERT."""
        self._session.add(user)
        self._session.flush()
        return user

    def save(self, user: User) -> User:
        """Flush pending changes to an existing ``user``."""
        self._session.add(user)
        self._session.flush()
        return user

    def deactivate(self, user: User) -> User:
        """Set ``is_active`` to ``False`` on ``user`` and flush the UPDATE."""
        user.is_active = False
        self._session.flush()
        return user
