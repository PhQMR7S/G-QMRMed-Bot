"""Reprice plans and design credits for the OpenAI reference-driven image pipeline.

Revision ID: 0018_openai_reference_pricing
Revises: 0017_runtime_schema_alignment
Create Date: 2026-09-15
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0018_openai_reference_pricing"
down_revision: str | Sequence[str] | None = "0017_runtime_schema_alignment"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    plans = sa.table(
        "plans",
        sa.column("code", sa.String()),
        sa.column("price", sa.Numeric()),
        sa.column("stars_price", sa.Integer()),
        sa.column("duration_days", sa.Integer()),
        sa.column("daily_limit", sa.Integer()),
    )
    op.execute(
        plans.update()
        .where(plans.c.code == "FREE")
        .values(price=0, stars_price=None, duration_days=None, daily_limit=1)
    )
    op.execute(
        plans.update()
        .where(plans.c.code == "PLUS")
        .values(price=15, stars_price=1200, duration_days=30, daily_limit=2)
    )
    op.execute(
        plans.update()
        .where(plans.c.code == "PRO")
        .values(price=50, stars_price=3850, duration_days=90, daily_limit=3)
    )

    credit_packs = sa.table(
        "credit_packs",
        sa.column("code", sa.String()),
        sa.column("stars_price", sa.Integer()),
    )
    op.execute(
        credit_packs.update()
        .where(credit_packs.c.code == "DESIGN_5")
        .values(stars_price=60)
    )
    op.execute(
        credit_packs.update()
        .where(credit_packs.c.code == "DESIGN_12")
        .values(stars_price=120)
    )
    op.execute(
        credit_packs.update()
        .where(credit_packs.c.code == "DESIGN_20")
        .values(stars_price=180)
    )


def downgrade() -> None:
    plans = sa.table(
        "plans",
        sa.column("code", sa.String()),
        sa.column("price", sa.Numeric()),
        sa.column("stars_price", sa.Integer()),
        sa.column("duration_days", sa.Integer()),
        sa.column("daily_limit", sa.Integer()),
    )
    op.execute(
        plans.update()
        .where(plans.c.code == "FREE")
        .values(price=0, stars_price=None, duration_days=None, daily_limit=3)
    )
    op.execute(
        plans.update()
        .where(plans.c.code == "PLUS")
        .values(price=5, stars_price=400, duration_days=30, daily_limit=8)
    )
    op.execute(
        plans.update()
        .where(plans.c.code == "PRO")
        .values(price=20, stars_price=1600, duration_days=90, daily_limit=15)
    )

    credit_packs = sa.table(
        "credit_packs",
        sa.column("code", sa.String()),
        sa.column("stars_price", sa.Integer()),
    )
    op.execute(
        credit_packs.update()
        .where(credit_packs.c.code == "DESIGN_5")
        .values(stars_price=50)
    )
    op.execute(
        credit_packs.update()
        .where(credit_packs.c.code == "DESIGN_12")
        .values(stars_price=100)
    )
    op.execute(
        credit_packs.update()
        .where(credit_packs.c.code == "DESIGN_20")
        .values(stars_price=150)
    )
