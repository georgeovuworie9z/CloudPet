"""SQLAlchemy declarative base.

All ORM models (added in later milestones) will inherit from ``Base`` so that
``Base.metadata`` is the single source of truth for Alembic migrations.
"""

from __future__ import annotations

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass
