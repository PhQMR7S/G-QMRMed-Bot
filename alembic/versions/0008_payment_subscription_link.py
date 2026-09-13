"""Link approved payments to the subscriptions they grant.

Revision ID: 0008_payment_subscription_link
Revises: 0007_generation_dispatch_state
Create Date: 2026-09-13
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0008_payment_subscription_link"
down_revision: str | Sequence[str] | None = "0007_generation_dispatch_state"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "payments",
        sa.Column("subscription_id", sa.Uuid(), nullable=True),
    )
    op.create_foreign_key(
        "fk_payments_subscription_id",
        "payments",
        "subscriptions",
        ["subscription_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        "ix_payments_subscription_id",
        "payments",
        ["subscription_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_payments_subscription_id", table_name="payments")
    op.drop_constraint("fk_payments_subscription_id", "payments", type_="foreignkey")
    op.drop_column("payments", "subscription_id")
