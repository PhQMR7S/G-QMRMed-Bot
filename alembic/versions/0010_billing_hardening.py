"""Add immutable billing audit data and Telegram Stars payment snapshots.

Revision ID: 0010_billing_hardening
Revises: 0009_launch_pricing
Create Date: 2026-09-13
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0010_billing_hardening"
down_revision: str | Sequence[str] | None = "0009_launch_pricing"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("plans", sa.Column("stars_price", sa.Integer(), nullable=True))
    op.create_check_constraint(
        "ck_plans_stars_price_positive", "plans", "stars_price IS NULL OR stars_price > 0"
    )

    op.add_column("payments", sa.Column("activation_code_id", sa.Uuid(), nullable=True))
    op.add_column("payments", sa.Column("invoice_payload", sa.String(length=128), nullable=True))
    op.add_column("payments", sa.Column("stars_amount", sa.Integer(), nullable=True))
    op.create_check_constraint(
        "ck_payment_stars_amount_positive",
        "payments",
        "stars_amount IS NULL OR stars_amount > 0",
    )
    op.create_unique_constraint("uq_payments_invoice_payload", "payments", ["invoice_payload"])
    op.create_foreign_key(
        "fk_payments_activation_code_id",
        "payments",
        "activation_codes",
        ["activation_code_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("ix_payments_invoice_payload", "payments", ["invoice_payload"])

    op.create_table(
        "billing_ledger",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=True),
        sa.Column("payment_id", sa.Uuid(), nullable=True),
        sa.Column("subscription_id", sa.Uuid(), nullable=True),
        sa.Column("plan_id", sa.Uuid(), nullable=True),
        sa.Column("amount", sa.Numeric(12, 2), nullable=True),
        sa.Column("currency", sa.String(length=8), nullable=True),
        sa.Column("stars_amount", sa.Integer(), nullable=True),
        sa.Column("metadata", sa.JSON(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["payment_id"], ["payments.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["subscription_id"], ["subscriptions.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["plan_id"], ["plans.id"], ondelete="SET NULL"),
    )
    op.create_index("ix_billing_ledger_event_type", "billing_ledger", ["event_type"])
    op.create_index("ix_billing_ledger_user_id", "billing_ledger", ["user_id"])
    op.create_index("ix_billing_ledger_payment_id", "billing_ledger", ["payment_id"])
    op.create_index("ix_billing_ledger_subscription_id", "billing_ledger", ["subscription_id"])

    op.execute(
        """
        CREATE OR REPLACE FUNCTION gqmrmed_block_billing_ledger_mutation()
        RETURNS trigger AS $$
        BEGIN
            RAISE EXCEPTION 'billing_ledger_is_append_only';
        END;
        $$ LANGUAGE plpgsql;
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_billing_ledger_no_update_delete
        BEFORE UPDATE OR DELETE ON billing_ledger
        FOR EACH ROW EXECUTE FUNCTION gqmrmed_block_billing_ledger_mutation();
        """
    )

    # Canonical launch Star amounts. Telegram states that Stars' acquisition cost
    # varies by user/region; these amounts target the agreed $5/$20 plan values
    # using Telegram's current $0.013 reward value per Star.
    plans = sa.table("plans", sa.column("code", sa.String()), sa.column("stars_price", sa.Integer()))
    op.execute(plans.update().where(plans.c.code == "FREE").values(stars_price=None))
    op.execute(plans.update().where(plans.c.code == "PLUS").values(stars_price=400))
    op.execute(plans.update().where(plans.c.code == "PRO").values(stars_price=1600))


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_billing_ledger_no_update_delete ON billing_ledger")
    op.execute("DROP FUNCTION IF EXISTS gqmrmed_block_billing_ledger_mutation()")
    op.drop_index("ix_billing_ledger_subscription_id", table_name="billing_ledger")
    op.drop_index("ix_billing_ledger_payment_id", table_name="billing_ledger")
    op.drop_index("ix_billing_ledger_user_id", table_name="billing_ledger")
    op.drop_index("ix_billing_ledger_event_type", table_name="billing_ledger")
    op.drop_table("billing_ledger")
    op.drop_index("ix_payments_invoice_payload", table_name="payments")
    op.drop_constraint("fk_payments_activation_code_id", "payments", type_="foreignkey")
    op.drop_constraint("uq_payments_invoice_payload", "payments", type_="unique")
    op.drop_constraint("ck_payment_stars_amount_positive", "payments", type_="check")
    op.drop_column("payments", "stars_amount")
    op.drop_column("payments", "invoice_payload")
    op.drop_column("payments", "activation_code_id")
    op.drop_constraint("ck_plans_stars_price_positive", "plans", type_="check")
    op.drop_column("plans", "stars_price")
