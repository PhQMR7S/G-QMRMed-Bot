"""Add heartbeat timestamp for generation worker liveness tracking."""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0014_job_heartbeat"
down_revision: str | Sequence[str] | None = "0013_result_image_bytes"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "generation_jobs",
        sa.Column("heartbeat_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("generation_jobs", "heartbeat_at")
