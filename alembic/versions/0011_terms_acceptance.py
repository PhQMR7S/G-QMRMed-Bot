"""Persist the user's purchase-terms acceptance timestamp.

Revision ID: 0011_terms_acceptance
Revises: 0010_billing_hardening
Create Date: 2026-09-13
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0011_terms_acceptance"
down_revision: str | Sequence[str] | None = "0010_billing_hardening"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("users", sa.Column("terms_accepted_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "terms_accepted_at")
