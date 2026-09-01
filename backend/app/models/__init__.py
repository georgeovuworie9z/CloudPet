"""ORM models package.

Importing this package imports every model module so that ``Base.metadata`` is
fully populated for Alembic (autogenerate and metadata comparison).
"""

from __future__ import annotations

from app.models.user import User

__all__ = ["User"]
