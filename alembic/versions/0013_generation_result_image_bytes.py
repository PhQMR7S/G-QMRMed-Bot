"""Add optional inline image bytes for durable Telegram delivery retry."""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0013_result_image_bytes"
down_revision: str | Sequence[str] | None = "0012_design_credit_packs"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "generation_results",
        sa.Column("image_bytes", sa.LargeBinary(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("generation_results", "image_bytes")
