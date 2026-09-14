from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum
from uuid import UUID

from sqlalchemy import BigInteger, Boolean, CheckConstraint, Date, DateTime, ForeignKey, Integer, JSON, Numeric, String, Text, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from gqmrmed.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class PlanCode(StrEnum):
    FREE = "FREE"
    PLUS = "PLUS"
    PRO = "PRO"


class SubscriptionStatus(StrEnum):
    PENDING = "PENDING"
    ACTIVE = "ACTIVE"
    EXPIRED = "EXPIRED"
    CANCELLED = "CANCELLED"


class ActivationCodeStatus(StrEnum):
    UNUSED = "UNUSED"
    ACTIVATED = "ACTIVATED"
    EXPIRED = "EXPIRED"
    REVOKED = "REVOKED"


class PaymentStatus(StrEnum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    REFUNDED = "REFUNDED"


class JobStatus(StrEnum):
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class UsageReservationStatus(StrEnum):
    RESERVED = "RESERVED"
    COMMITTED = "COMMITTED"
    RELEASED = "RELEASED"


class UsageReservationSource(StrEnum):
    DAILY = "DAILY"
    CREDIT = "CREDIT"


class User(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint("design_credits >= 0", name="ck_users_design_credits_nonnegative"),
    )

    telegram_id: Mapped[int] = mapped_column(BigInteger, unique=True, nullable=False, index=True)
    username: Mapped[str | None] = mapped_column(String(255))
    first_name: Mapped[str | None] = mapped_column(String(255))
    last_name: Mapped[str | None] = mapped_column(String(255))
    language: Mapped[str] = mapped_column(String(16), default="en", nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    terms_accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    design_credits: Mapped[int] = mapped_column(Integer, default=0, nullable=False)


class Plan(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "plans"
    __table_args__ = (
        CheckConstraint("price >= 0", name="ck_plans_price_nonnegative"),
        CheckConstraint("stars_price IS NULL OR stars_price > 0", name="ck_plans_stars_price_positive"),
        CheckConstraint("duration_days IS NULL OR duration_days > 0", name="ck_plans_duration_positive"),
        CheckConstraint("daily_limit IS NULL OR daily_limit > 0", name="ck_plans_daily_limit_positive"),
    )

    name: Mapped[str] = mapped_column(String(128), nullable=False)
    code: Mapped[str] = mapped_column(String(16), unique=True, nullable=False)
    price: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(8), default="USD", nullable=False)
    stars_price: Mapped[int | None] = mapped_column(Integer)
    duration_days: Mapped[int | None] = mapped_column(Integer)
    daily_limit: Mapped[int | None] = mapped_column(Integer)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class CreditPack(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "credit_packs"
    __table_args__ = (
        CheckConstraint("stars_price > 0", name="ck_credit_packs_stars_positive"),
        CheckConstraint("credits > 0", name="ck_credit_packs_credits_positive"),
    )

    name: Mapped[str] = mapped_column(String(128), nullable=False)
    code: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    credits: Mapped[int] = mapped_column(Integer, nullable=False)
    stars_price: Mapped[int] = mapped_column(Integer, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class Subscription(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "subscriptions"

    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    plan_id: Mapped[UUID] = mapped_column(ForeignKey("plans.id"), nullable=False)
    status: Mapped[str] = mapped_column(String(16), default=SubscriptionStatus.PENDING, nullable=False)
    starts_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    activated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ActivationCode(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "activation_codes"
    __table_args__ = (CheckConstraint("duration_days > 0", name="ck_activation_duration_positive"),)

    code_hash: Mapped[str] = mapped_column(String(128), unique=True, nullable=False, index=True)
    plan_id: Mapped[UUID] = mapped_column(ForeignKey("plans.id"), nullable=False)
    duration_days: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(16), default=ActivationCodeStatus.UNUSED, nullable=False)
    activated_by_user_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"))
    activated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Payment(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "payments"
    __table_args__ = (
        UniqueConstraint("provider", "transaction_id", name="uq_payments_provider_transaction"),
        UniqueConstraint("invoice_payload", name="uq_payments_invoice_payload"),
    )

    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    plan_id: Mapped[UUID | None] = mapped_column(ForeignKey("plans.id"))
    subscription_id: Mapped[UUID | None] = mapped_column(ForeignKey("subscriptions.id"))
    activation_code_id: Mapped[UUID | None] = mapped_column(ForeignKey("activation_codes.id"))
    credit_pack_id: Mapped[UUID | None] = mapped_column(ForeignKey("credit_packs.id"))
    provider: Mapped[str] = mapped_column(String(32), nullable=False)
    transaction_id: Mapped[str | None] = mapped_column(String(255))
    invoice_payload: Mapped[str | None] = mapped_column(String(255))
    stars_amount: Mapped[int | None] = mapped_column(Integer)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(8), nullable=False)
    status: Mapped[str] = mapped_column(String(16), default=PaymentStatus.PENDING, nullable=False)
    approved_by: Mapped[UUID | None] = mapped_column(ForeignKey("admin_users.id"))


class DailyUsage(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "daily_usage"
    __table_args__ = (
        UniqueConstraint("user_id", "usage_date", name="uq_daily_usage_user_date"),
        CheckConstraint("reserved >= 0 AND committed >= 0", name="ck_daily_usage_nonnegative"),
    )

    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    usage_date: Mapped[date] = mapped_column(Date, nullable=False)
    reserved: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    committed: Mapped[int] = mapped_column(Integer, default=0, nullable=False)


class GenerationJob(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "generation_jobs"
    __table_args__ = (
        CheckConstraint("progress >= 0 AND progress <= 100", name="ck_generation_progress_range"),
    )

    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    input_type: Mapped[str] = mapped_column(String(32), nullable=False)
    input_text: Mapped[str | None] = mapped_column(Text)
    input_storage_key: Mapped[str | None] = mapped_column(String(1024))
    input_mime_type: Mapped[str | None] = mapped_column(String(128))
    input_metadata: Mapped[dict[str, object] | None] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(16), default=JobStatus.QUEUED, nullable=False)
    stage: Mapped[str | None] = mapped_column(String(64))
    progress: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    error: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    heartbeat_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    dispatch_attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    enqueued_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_dispatch_error: Mapped[str | None] = mapped_column(Text)

    @property
    def current_stage(self) -> str | None:
        return self.stage

    @current_stage.setter
    def current_stage(self, value: str | None) -> None:
        self.stage = value


class GenerationResult(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "generation_results"
    __table_args__ = (
        CheckConstraint("width > 0 AND height > 0", name="ck_generation_dimensions_positive"),
    )

    job_id: Mapped[UUID] = mapped_column(ForeignKey("generation_jobs.id", ondelete="CASCADE"), nullable=False, unique=True)
    storage_key: Mapped[str] = mapped_column(String(1024), nullable=False)
    mime_type: Mapped[str] = mapped_column(String(128), nullable=False)
    width: Mapped[int] = mapped_column(Integer, nullable=False)
    height: Mapped[int] = mapped_column(Integer, nullable=False)
    image_bytes: Mapped[bytes | None] = mapped_column()


class AdminUser(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "admin_users"

    telegram_id: Mapped[int] = mapped_column(BigInteger, unique=True, nullable=False, index=True)
    username: Mapped[str | None] = mapped_column(String(255))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    role: Mapped[str] = mapped_column(String(32), default="admin", nullable=False)


class AdminAction(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "admin_actions"

    admin_user_id: Mapped[UUID] = mapped_column(ForeignKey("admin_users.id", ondelete="CASCADE"), nullable=False)
    action: Mapped[str] = mapped_column(String(128), nullable=False)
    target_type: Mapped[str | None] = mapped_column(String(64))
    target_id: Mapped[UUID | None] = mapped_column(Uuid)
    action_metadata: Mapped[dict[str, object] | None] = mapped_column("metadata", JSON)


class SystemSetting(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "system_settings"

    key: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    value: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)


class UsageReservation(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "usage_reservations"
    __table_args__ = (
        UniqueConstraint("job_id", name="uq_usage_reservations_job_id"),
        CheckConstraint("source IN ('DAILY', 'CREDIT')", name="ck_usage_reservations_source"),
    )

    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    job_id: Mapped[UUID] = mapped_column(ForeignKey("generation_jobs.id", ondelete="CASCADE"), nullable=False)
    usage_date: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(String(16), default=UsageReservationStatus.RESERVED, nullable=False)
    source: Mapped[str] = mapped_column(String(16), default=UsageReservationSource.DAILY, nullable=False)
    reserved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    settled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class GenerationDispatchState(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "generation_dispatch_state"

    job_id: Mapped[UUID] = mapped_column(ForeignKey("generation_jobs.id", ondelete="CASCADE"), nullable=False, unique=True)
    dispatch_status: Mapped[str] = mapped_column(String(32), default="QUEUED", nullable=False)
    attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_error: Mapped[str | None] = mapped_column(Text)
    dispatched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class BillingLedger(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "billing_ledger"

    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    user_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"))
    payment_id: Mapped[UUID | None] = mapped_column(ForeignKey("payments.id"))
    subscription_id: Mapped[UUID | None] = mapped_column(ForeignKey("subscriptions.id"))
    plan_id: Mapped[UUID | None] = mapped_column(ForeignKey("plans.id"))
    amount: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    currency: Mapped[str | None] = mapped_column(String(8))
    stars_amount: Mapped[int | None] = mapped_column(Integer)
    ledger_metadata: Mapped[dict[str, object] | None] = mapped_column("metadata", JSON)
