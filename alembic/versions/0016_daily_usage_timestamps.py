"""Add timestamp columns required by the daily usage ORM model.

Revision ID: 0016_daily_usage_timestamps
Revises: 0015_reservation_reserved_at
Create Date: 2026-09-14
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0016_daily_usage_timestamps"
down_revision: str | Sequence[str] | None = "0015_reservation_reserved_at"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "daily_usage",
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.add_column(
        "daily_usage",
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )


def downgrade() -> None:
    op.drop_column("daily_usage", "updated_at")
    op.drop_column("daily_usage", "created_at")
