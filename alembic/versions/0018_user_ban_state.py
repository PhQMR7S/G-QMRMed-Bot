"""Add persistent moderation state for user bans.

Revision ID: 0018_user_ban_state
Revises: 0017_runtime_schema_alignment
Create Date: 2026-09-14
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0018_user_ban_state"
down_revision: str | Sequence[str] | None = "0017_runtime_schema_alignment"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("is_banned", sa.Boolean(), server_default=sa.false(), nullable=False),
    )


def downgrade() -> None:
    op.drop_column("users", "is_banned")
