"""create pets table

Revision ID: ac7cade63b8a
Revises: 2d1af88f2904
Create Date: 2026-09-03 21:14:37.602263+00:00

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "ac7cade63b8a"
down_revision: str | None = "2d1af88f2904"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "pets",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("owner_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("species", sa.String(length=50), nullable=False),
        sa.Column("breed", sa.String(length=100), nullable=True),
        sa.Column("sex", sa.String(length=20), nullable=False),
        sa.Column("date_of_birth", sa.Date(), nullable=True),
        sa.Column("weight", sa.Numeric(precision=6, scale=2), nullable=True),
        sa.Column("description", sa.String(length=1000), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["owner_id"],
            ["users.id"],
            name="fk_pets_owner_id_users",
            ondelete="NO ACTION",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_pets_owner_id", "pets", ["owner_id"])


def downgrade() -> None:
    op.drop_index("ix_pets_owner_id", table_name="pets")
    op.drop_table("pets")
