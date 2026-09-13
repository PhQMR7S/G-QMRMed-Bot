"""Set launch pricing and fair-use generation limits.

Revision ID: 0009_launch_pricing
Revises: 0008_payment_subscription_link
Create Date: 2026-09-13
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0009_launch_pricing"
down_revision: str | Sequence[str] | None = "0008_payment_subscription_link"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    plans = sa.table(
        "plans",
        sa.column("code", sa.String()),
        sa.column("price", sa.Numeric()),
        sa.column("duration_days", sa.Integer()),
        sa.column("daily_limit", sa.Integer()),
    )

    # Launch policy: keep FREE unchanged, replace unlimited paid usage with
    # predictable fair-use ceilings so subscription revenue can fund compute.
    op.execute(
        plans.update()
        .where(plans.c.code == "PLUS")
        .values(price=5, duration_days=30, daily_limit=8)
    )
    op.execute(
        plans.update()
        .where(plans.c.code == "PRO")
        .values(price=20, duration_days=90, daily_limit=15)
    )


def downgrade() -> None:
    plans = sa.table(
        "plans",
        sa.column("code", sa.String()),
        sa.column("price", sa.Numeric()),
        sa.column("duration_days", sa.Integer()),
        sa.column("daily_limit", sa.Integer()),
    )
    op.execute(
        plans.update()
        .where(plans.c.code == "PLUS")
        .values(price=5, duration_days=30, daily_limit=None)
    )
    op.execute(
        plans.update()
        .where(plans.c.code == "PRO")
        .values(price=20, duration_days=365, daily_limit=None)
    )
