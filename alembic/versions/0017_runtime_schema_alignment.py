"""Align remaining runtime tables with the current ORM contract.

Revision ID: 0017_runtime_schema_alignment
Revises: 0016_daily_usage_timestamps
Create Date: 2026-09-14
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0017_runtime_schema_alignment"
down_revision: str | Sequence[str] | None = "0016_daily_usage_timestamps"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Activation service writes ActivationCode.activated_by_user_id.
    if (
        op.get_bind()
        .dialect.has_table(op.get_bind(), "activation_codes")
    ):
        columns = {
            row[0]
            for row in op.get_bind().exec_driver_sql(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_schema='public' AND table_name='activation_codes'"
            ).fetchall()
        }
        if "activated_by" in columns and "activated_by_user_id" not in columns:
            op.alter_column("activation_codes", "activated_by", new_column_name="activated_by_user_id")

    # BillingLedger inherits TimestampMixin and is written during paid credit grants.
    op.add_column(
        "billing_ledger",
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.add_column(
        "billing_ledger",
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # AdminAction also inherits TimestampMixin and its ORM field maps to metadata.
    op.add_column(
        "admin_actions",
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    columns = {
        row[0]
        for row in op.get_bind().exec_driver_sql(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_schema='public' AND table_name='admin_actions'"
        ).fetchall()
    }
    if "details" in columns and "metadata" not in columns:
        op.alter_column("admin_actions", "details", new_column_name="metadata")

    # Durable dispatch state is part of the current ORM contract.
    op.create_table(
        "generation_dispatch_state",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("job_id", sa.Uuid(), nullable=False),
        sa.Column("dispatch_status", sa.String(length=32), server_default="QUEUED", nullable=False),
        sa.Column("attempts", sa.Integer(), server_default="0", nullable=False),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("dispatched_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["job_id"], ["generation_jobs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("job_id", name="uq_generation_dispatch_state_job_id"),
        sa.CheckConstraint("attempts >= 0", name="ck_generation_dispatch_attempts_nonnegative"),
    )


def downgrade() -> None:
    op.drop_table("generation_dispatch_state")
    op.alter_column("admin_actions", "metadata", new_column_name="details")
    op.drop_column("admin_actions", "updated_at")
    op.drop_column("billing_ledger", "updated_at")
    op.drop_column("billing_ledger", "created_at")
    op.alter_column("activation_codes", "activated_by_user_id", new_column_name="activated_by")
