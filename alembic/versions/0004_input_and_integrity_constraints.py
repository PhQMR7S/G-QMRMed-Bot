"""Add arbitrary-input fields and database integrity constraints.

Revision ID: 0004_input_and_integrity_constraints
Revises: 0003_widen_telegram_id
Create Date: 2026-09-13
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0004_input_and_integrity_constraints"
down_revision: str | Sequence[str] | None = "0003_widen_telegram_id"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("generation_jobs", sa.Column("input_storage_key", sa.String(length=1024)))
    op.add_column("generation_jobs", sa.Column("input_mime_type", sa.String(length=128)))
    op.add_column("generation_jobs", sa.Column("input_metadata", sa.JSON()))

    op.create_check_constraint(
        "ck_plans_price_nonnegative",
        "plans",
        "price >= 0",
    )
    op.create_check_constraint(
        "ck_plans_duration_positive",
        "plans",
        "duration_days IS NULL OR duration_days > 0",
    )
    op.create_check_constraint(
        "ck_plans_daily_limit_positive",
        "plans",
        "daily_limit IS NULL OR daily_limit > 0",
    )
    op.create_check_constraint(
        "ck_daily_usage_nonnegative",
        "daily_usage",
        "reserved >= 0 AND committed >= 0",
    )
    op.create_check_constraint(
        "ck_generation_progress_range",
        "generation_jobs",
        "progress >= 0 AND progress <= 100",
    )
    op.create_check_constraint(
        "ck_generation_dimensions_positive",
        "generation_results",
        "width > 0 AND height > 0",
    )
    op.create_check_constraint(
        "ck_activation_duration_positive",
        "activation_codes",
        "duration_days > 0",
    )
    op.create_check_constraint(
        "ck_payment_amount_nonnegative",
        "payments",
        "amount >= 0",
    )


def downgrade() -> None:
    op.drop_constraint("ck_payment_amount_nonnegative", "payments", type_="check")
    op.drop_constraint("ck_activation_duration_positive", "activation_codes", type_="check")
    op.drop_constraint("ck_generation_dimensions_positive", "generation_results", type_="check")
    op.drop_constraint("ck_generation_progress_range", "generation_jobs", type_="check")
    op.drop_constraint("ck_daily_usage_nonnegative", "daily_usage", type_="check")
    op.drop_constraint("ck_plans_daily_limit_positive", "plans", type_="check")
    op.drop_constraint("ck_plans_duration_positive", "plans", type_="check")
    op.drop_constraint("ck_plans_price_nonnegative", "plans", type_="check")

    op.drop_column("generation_jobs", "input_metadata")
    op.drop_column("generation_jobs", "input_mime_type")
    op.drop_column("generation_jobs", "input_storage_key")
