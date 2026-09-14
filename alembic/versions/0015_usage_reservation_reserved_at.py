"""Add reservation timestamp to the usage reservation ledger."""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0015_reservation_reserved_at"
down_revision: str | Sequence[str] | None = "0014_job_heartbeat"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "usage_reservations",
        sa.Column(
            "reserved_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_column("usage_reservations", "reserved_at")
