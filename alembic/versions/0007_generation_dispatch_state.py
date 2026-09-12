"""Add durable generation dispatch state for at-least-once queue delivery.

Revision ID: 0007_generation_dispatch_state
Revises: 0006_usage_reservation_ledger
Create Date: 2026-09-13
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0007_generation_dispatch_state"
down_revision: str | Sequence[str] | None = "0006_usage_reservation_ledger"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "generation_jobs",
        sa.Column("dispatch_attempts", sa.Integer(), server_default="0", nullable=False),
    )
    op.add_column(
        "generation_jobs",
        sa.Column("enqueued_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "generation_jobs",
        sa.Column("last_dispatch_error", sa.Text(), nullable=True),
    )
    op.create_check_constraint(
        "ck_generation_dispatch_attempts_nonnegative",
        "generation_jobs",
        "dispatch_attempts >= 0",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_generation_dispatch_attempts_nonnegative",
        "generation_jobs",
        type_="check",
    )
    op.drop_column("generation_jobs", "last_dispatch_error")
    op.drop_column("generation_jobs", "enqueued_at")
    op.drop_column("generation_jobs", "dispatch_attempts")
