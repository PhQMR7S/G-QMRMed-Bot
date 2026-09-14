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
        sa.Column("id", sa.Uuid(), primary_key=True, nullable=False, server_default=sa.text("gen_random_uuid()")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("code", sa.String(length=32), nullable=False),
        sa.Column("credits", sa.Integer(), nullable=False),
        sa.Column("stars_price", sa.Integer(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.CheckConstraint("stars_price > 0", name="ck_credit_packs_stars_positive"),
        sa.CheckConstraint("credits > 0", name="ck_credit_packs_credits_positive"),
        sa.UniqueConstraint("code", name="uq_credit_packs_code"),
    )
    op.execute("ALTER TABLE credit_packs ENABLE ROW LEVEL SECURITY")

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

    op.execute(
        sa.text(
            "INSERT INTO credit_packs (name, code, credits, stars_price, is_active) VALUES "
            "('5 تصاميم', 'DESIGN_5', 5, 50, true), "
            "('12 تصميماً', 'DESIGN_12', 12, 100, true), "
            "('20 تصميماً', 'DESIGN_20', 20, 150, true)"
        )
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
