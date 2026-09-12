"""Seed the initial GQMRMed subscription plans.

Revision ID: 0002_seed_plans
Revises: 0001_initial_schema
Create Date: 2026-09-13
"""
from collections.abc import Sequence
from uuid import UUID

import sqlalchemy as sa
from alembic import op

revision: str = "0002_seed_plans"
down_revision: str | Sequence[str] | None = "0001_initial_schema"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


FREE_PLAN_ID = UUID("11111111-1111-4111-8111-111111111111")
PLUS_PLAN_ID = UUID("22222222-2222-4222-8222-222222222222")
PRO_PLAN_ID = UUID("33333333-3333-4333-8333-333333333333")


def upgrade() -> None:
    plans = sa.table(
        "plans",
        sa.column("id", sa.Uuid()),
        sa.column("name", sa.String()),
        sa.column("code", sa.String()),
        sa.column("price", sa.Numeric()),
        sa.column("currency", sa.String()),
        sa.column("duration_days", sa.Integer()),
        sa.column("daily_limit", sa.Integer()),
        sa.column("is_active", sa.Boolean()),
    )
    op.bulk_insert(
        plans,
        [
            {
                "id": FREE_PLAN_ID,
                "name": "FREE",
                "code": "FREE",
                "price": 0,
                "currency": "USD",
                "duration_days": None,
                "daily_limit": 3,
                "is_active": True,
            },
            {
                "id": PLUS_PLAN_ID,
                "name": "PLUS",
                "code": "PLUS",
                "price": 5,
                "currency": "USD",
                "duration_days": 30,
                "daily_limit": None,
                "is_active": True,
            },
            {
                "id": PRO_PLAN_ID,
                "name": "PRO",
                "code": "PRO",
                "price": 20,
                "currency": "USD",
                "duration_days": 365,
                "daily_limit": None,
                "is_active": True,
            },
        ],
    )


def downgrade() -> None:
    plans = sa.table("plans", sa.column("code", sa.String()))
    op.execute(plans.delete().where(plans.c.code.in_(["FREE", "PLUS", "PRO"])))
