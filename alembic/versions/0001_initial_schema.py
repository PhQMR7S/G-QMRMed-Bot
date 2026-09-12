"""Create the initial GQMRMed production schema.

Revision ID: 0001_initial_schema
Revises:
Create Date: 2026-09-13
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0001_initial_schema"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table("admin_users", sa.Column("id", sa.Uuid(), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False), sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False), sa.Column("username", sa.String(128), nullable=False), sa.Column("password_hash", sa.String(255), nullable=False), sa.Column("is_active", sa.Boolean(), nullable=False), sa.PrimaryKeyConstraint("id", name="pk_admin_users"), sa.UniqueConstraint("username", name="uq_admin_users_username"))
    op.create_table("plans", sa.Column("id", sa.Uuid(), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False), sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False), sa.Column("name", sa.String(64), nullable=False), sa.Column("code", sa.String(16), nullable=False), sa.Column("price", sa.Numeric(12, 2), nullable=False), sa.Column("currency", sa.String(8), nullable=False), sa.Column("duration_days", sa.Integer(), nullable=True), sa.Column("daily_limit", sa.Integer(), nullable=True), sa.Column("is_active", sa.Boolean(), nullable=False), sa.PrimaryKeyConstraint("id", name="pk_plans"), sa.UniqueConstraint("code", name="uq_plans_code"))
    op.create_table("users", sa.Column("id", sa.Uuid(), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False), sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False), sa.Column("telegram_id", sa.Integer(), nullable=False), sa.Column("username", sa.String(255), nullable=True), sa.Column("first_name", sa.String(255), nullable=True), sa.Column("last_name", sa.String(255), nullable=True), sa.Column("language", sa.String(16), nullable=False), sa.Column("is_active", sa.Boolean(), nullable=False), sa.PrimaryKeyConstraint("id", name="pk_users"), sa.UniqueConstraint("telegram_id", name="uq_users_telegram_id"))
    op.create_index("ix_users_telegram_id", "users", ["telegram_id"], unique=False)

    op.create_table("activation_codes", sa.Column("id", sa.Uuid(), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False), sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False), sa.Column("code_hash", sa.String(128), nullable=False), sa.Column("plan_id", sa.Uuid(), nullable=False), sa.Column("duration_days", sa.Integer(), nullable=False), sa.Column("status", sa.String(16), nullable=False), sa.Column("created_by", sa.Uuid(), nullable=True), sa.Column("activated_by", sa.Uuid(), nullable=True), sa.Column("activated_at", sa.DateTime(timezone=True), nullable=True), sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True), sa.ForeignKeyConstraint(["activated_by"], ["users.id"]), sa.ForeignKeyConstraint(["created_by"], ["admin_users.id"]), sa.ForeignKeyConstraint(["plan_id"], ["plans.id"]), sa.PrimaryKeyConstraint("id", name="pk_activation_codes"), sa.UniqueConstraint("code_hash", name="uq_activation_codes_code_hash"))
    op.create_index("ix_activation_codes_code_hash", "activation_codes", ["code_hash"], unique=False)

    op.create_table("subscriptions", sa.Column("id", sa.Uuid(), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False), sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False), sa.Column("user_id", sa.Uuid(), nullable=False), sa.Column("plan_id", sa.Uuid(), nullable=False), sa.Column("status", sa.String(16), nullable=False), sa.Column("starts_at", sa.DateTime(timezone=True), nullable=True), sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True), sa.Column("activated_at", sa.DateTime(timezone=True), nullable=True), sa.ForeignKeyConstraint(["plan_id"], ["plans.id"]), sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"), sa.PrimaryKeyConstraint("id", name="pk_subscriptions"))
    op.create_index("ix_subscriptions_user_id", "subscriptions", ["user_id"], unique=False)

    op.create_table("payments", sa.Column("id", sa.Uuid(), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False), sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False), sa.Column("user_id", sa.Uuid(), nullable=False), sa.Column("plan_id", sa.Uuid(), nullable=False), sa.Column("provider", sa.String(64), nullable=False), sa.Column("transaction_id", sa.String(255), nullable=True), sa.Column("amount", sa.Numeric(12, 2), nullable=False), sa.Column("currency", sa.String(8), nullable=False), sa.Column("status", sa.String(16), nullable=False), sa.Column("approved_by", sa.Uuid(), nullable=True), sa.ForeignKeyConstraint(["approved_by"], ["admin_users.id"]), sa.ForeignKeyConstraint(["plan_id"], ["plans.id"]), sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"), sa.PrimaryKeyConstraint("id", name="pk_payments"))
    op.create_index("ix_payments_user_id", "payments", ["user_id"], unique=False)
    op.create_index("ix_payments_transaction_id", "payments", ["transaction_id"], unique=False)

    op.create_table("daily_usage", sa.Column("id", sa.Uuid(), nullable=False), sa.Column("user_id", sa.Uuid(), nullable=False), sa.Column("usage_date", sa.Date(), nullable=False), sa.Column("reserved", sa.Integer(), nullable=False), sa.Column("committed", sa.Integer(), nullable=False), sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"), sa.PrimaryKeyConstraint("id", name="pk_daily_usage"), sa.UniqueConstraint("user_id", "usage_date", name="uq_daily_usage_user_date"))
    op.create_index("ix_daily_usage_user_id", "daily_usage", ["user_id"], unique=False)
    op.create_index("ix_daily_usage_usage_date", "daily_usage", ["usage_date"], unique=False)

    op.create_table("generation_jobs", sa.Column("id", sa.Uuid(), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False), sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False), sa.Column("user_id", sa.Uuid(), nullable=False), sa.Column("input_type", sa.String(32), nullable=False), sa.Column("input_text", sa.Text(), nullable=True), sa.Column("status", sa.String(16), nullable=False), sa.Column("progress", sa.Integer(), nullable=False), sa.Column("current_stage", sa.String(64), nullable=True), sa.Column("started_at", sa.DateTime(timezone=True), nullable=True), sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True), sa.Column("error", sa.Text(), nullable=True), sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"), sa.PrimaryKeyConstraint("id", name="pk_generation_jobs"))
    op.create_index("ix_generation_jobs_user_id", "generation_jobs", ["user_id"], unique=False)
    op.create_index("ix_generation_jobs_status", "generation_jobs", ["status"], unique=False)

    op.create_table("generation_results", sa.Column("id", sa.Uuid(), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False), sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False), sa.Column("job_id", sa.Uuid(), nullable=False), sa.Column("storage_key", sa.String(1024), nullable=False), sa.Column("mime_type", sa.String(128), nullable=False), sa.Column("width", sa.Integer(), nullable=False), sa.Column("height", sa.Integer(), nullable=False), sa.ForeignKeyConstraint(["job_id"], ["generation_jobs.id"], ondelete="CASCADE"), sa.PrimaryKeyConstraint("id", name="pk_generation_results"), sa.UniqueConstraint("job_id", name="uq_generation_results_job_id"))

    op.create_table("admin_actions", sa.Column("id", sa.Uuid(), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False), sa.Column("admin_user_id", sa.Uuid(), nullable=False), sa.Column("action", sa.String(128), nullable=False), sa.Column("target_type", sa.String(64), nullable=True), sa.Column("target_id", sa.Uuid(), nullable=True), sa.Column("details", sa.Text(), nullable=True), sa.ForeignKeyConstraint(["admin_user_id"], ["admin_users.id"], ondelete="CASCADE"), sa.PrimaryKeyConstraint("id", name="pk_admin_actions"))
    op.create_index("ix_admin_actions_admin_user_id", "admin_actions", ["admin_user_id"], unique=False)

    op.create_table("system_settings", sa.Column("id", sa.Uuid(), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False), sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False), sa.Column("key", sa.String(128), nullable=False), sa.Column("value", sa.Text(), nullable=False), sa.PrimaryKeyConstraint("id", name="pk_system_settings"), sa.UniqueConstraint("key", name="uq_system_settings_key"))


def downgrade() -> None:
    op.drop_table("system_settings")
    op.drop_index("ix_admin_actions_admin_user_id", table_name="admin_actions")
    op.drop_table("admin_actions")
    op.drop_table("generation_results")
    op.drop_index("ix_generation_jobs_status", table_name="generation_jobs")
    op.drop_index("ix_generation_jobs_user_id", table_name="generation_jobs")
    op.drop_table("generation_jobs")
    op.drop_index("ix_daily_usage_usage_date", table_name="daily_usage")
    op.drop_index("ix_daily_usage_user_id", table_name="daily_usage")
    op.drop_table("daily_usage")
    op.drop_index("ix_payments_transaction_id", table_name="payments")
    op.drop_index("ix_payments_user_id", table_name="payments")
    op.drop_table("payments")
    op.drop_index("ix_subscriptions_user_id", table_name="subscriptions")
    op.drop_table("subscriptions")
    op.drop_index("ix_activation_codes_code_hash", table_name="activation_codes")
    op.drop_table("activation_codes")
    op.drop_index("ix_users_telegram_id", table_name="users")
    op.drop_table("users")
    op.drop_table("plans")
    op.drop_table("admin_users")
