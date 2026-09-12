"""Prevent duplicate payment provider transactions.

Revision ID: 0005_payment_idempotency
Revises: 0004_input_and_integrity_constraints
Create Date: 2026-09-13
"""
from collections.abc import Sequence

from alembic import op

revision: str = "0005_payment_idempotency"
down_revision: str | Sequence[str] | None = "0004_input_and_integrity_constraints"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_unique_constraint(
        "uq_payments_provider_transaction",
        "payments",
        ["provider", "transaction_id"],
    )


def downgrade() -> None:
    op.drop_constraint("uq_payments_provider_transaction", "payments", type_="unique")
