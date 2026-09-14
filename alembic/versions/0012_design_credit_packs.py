"""Add durable purchased design credits and Telegram Stars packs.

Revision ID: 0012_design_credit_packs
Revises: 0011_terms_acceptance
Create Date: 2026-09-14
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0012_design_credit_packs"
down_revision: str | Sequence[str] | None = "0011_terms_acceptance"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("users", sa.Column("design_credits", sa.Integer(), nullable=False, server_default="0"))
    op.create_check_constraint("ck_users_design_credits_nonnegative", "users", "design_credits >= 0")

    op.create_table(
        "credit_packs",
        sa.Column("id", sa.Uuid(), primary_key=True, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("code", sa.String(length=32), nullable=False),
        sa.Column("credits", sa.Integer(), nullable=False),
        sa.Column("stars_price", sa.Integer(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.CheckConstraint("stars_price > 0", name="ck_credit_packs_stars_positive"),
        sa.CheckConstraint("credits > 0", name="ck_credit_packs_credits_positive"),
        sa.UniqueConstraint("code", name="uq_credit_packs_code"),
    )

    op.add_column("payments", sa.Column("credit_pack_id", sa.Uuid(), nullable=True))
    op.alter_column("payments", "plan_id", nullable=True)
    op.create_foreign_key("fk_payments_credit_pack_id", "payments", "credit_packs", ["credit_pack_id"], ["id"])

    op.add_column(
        "usage_reservations",
        sa.Column("source", sa.String(length=16), nullable=False, server_default="DAILY"),
    )
    op.create_check_constraint(
        "ck_usage_reservation_source", "usage_reservations", "source IN ('DAILY', 'CREDIT')"
    )

    credit_packs = sa.table(
        "credit_packs",
        sa.column("id", sa.Uuid()),
        sa.column("created_at", sa.DateTime(timezone=True)),
        sa.column("updated_at", sa.DateTime(timezone=True)),
        sa.column("name", sa.String()),
        sa.column("code", sa.String()),
        sa.column("credits", sa.Integer()),
        sa.column("stars_price", sa.Integer()),
        sa.column("is_active", sa.Boolean()),
    )
    now = sa.func.now()
    op.bulk_insert(
        credit_packs,
        [
            {"id": sa.text("gen_random_uuid()"), "created_at": now, "updated_at": now, "name": "5 تصاميم", "code": "DESIGN_5", "credits": 5, "stars_price": 50, "is_active": True},
            {"id": sa.text("gen_random_uuid()"), "created_at": now, "updated_at": now, "name": "12 تصميماً", "code": "DESIGN_12", "credits": 12, "stars_price": 100, "is_active": True},
            {"id": sa.text("gen_random_uuid()"), "created_at": now, "updated_at": now, "name": "20 تصميماً", "code": "DESIGN_20", "credits": 20, "stars_price": 150, "is_active": True},
        ],
    )


def downgrade() -> None:
    op.drop_constraint("ck_usage_reservation_source", "usage_reservations", type_="check")
    op.drop_column("usage_reservations", "source")
    op.drop_constraint("fk_payments_credit_pack_id", "payments", type_="foreignkey")
    op.drop_column("payments", "credit_pack_id")
    op.alter_column("payments", "plan_id", nullable=False)
    op.drop_table("credit_packs")
    op.drop_constraint("ck_users_design_credits_nonnegative", "users", type_="check")
    op.drop_column("users", "design_credits")
