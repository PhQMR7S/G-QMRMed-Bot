"""Add a durable, job-scoped usage reservation ledger.

Revision ID: 0006_usage_reservation_ledger
Revises: 0005_payment_idempotency
Create Date: 2026-09-13
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0006_usage_reservation_ledger"
down_revision: str | Sequence[str] | None = "0005_payment_idempotency"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "usage_reservations",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("job_id", sa.Uuid(), nullable=False),
        sa.Column("usage_date", sa.Date(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("settled_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "status IN ('RESERVED', 'COMMITTED', 'RELEASED')",
            name="ck_usage_reservation_status",
        ),
        sa.ForeignKeyConstraint(
            ["job_id"],
            ["generation_jobs.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_usage_reservations"),
        sa.UniqueConstraint("job_id", name="uq_usage_reservations_job_id"),
    )
    op.create_index(
        "ix_usage_reservations_user_id",
        "usage_reservations",
        ["user_id"],
    )
    op.create_index(
        "ix_usage_reservations_job_id",
        "usage_reservations",
        ["job_id"],
    )
    op.create_index(
        "ix_usage_reservations_usage_date",
        "usage_reservations",
        ["usage_date"],
    )


def downgrade() -> None:
    op.drop_index("ix_usage_reservations_usage_date", table_name="usage_reservations")
    op.drop_index("ix_usage_reservations_job_id", table_name="usage_reservations")
    op.drop_index("ix_usage_reservations_user_id", table_name="usage_reservations")
    op.drop_table("usage_reservations")
