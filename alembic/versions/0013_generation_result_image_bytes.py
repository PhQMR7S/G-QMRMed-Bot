"""Add optional inline image bytes for durable Telegram delivery retry."""

from alembic import op
import sqlalchemy as sa


revision = "0013_generation_result_image_bytes"
down_revision = "0012_design_credit_packs"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "generation_results",
        sa.Column("image_bytes", sa.LargeBinary(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("generation_results", "image_bytes")
