from sqlalchemy import BigInteger, Uuid

from gqmrmed.db.base import Base
from gqmrmed.db.models import (
    ActivationCode,
    DailyUsage,
    GenerationJob,
    GenerationResult,
    Payment,
    Plan,
    Subscription,
    UsageReservation,
    User,
)


def test_core_tables_are_registered() -> None:
    expected = {
        "users",
        "plans",
        "subscriptions",
        "activation_codes",
        "payments",
        "daily_usage",
        "generation_jobs",
        "usage_reservations",
        "generation_results",
        "admin_users",
        "admin_actions",
        "system_settings",
    }
    assert expected.issubset(Base.metadata.tables)


def test_telegram_id_uses_bigint() -> None:
    assert isinstance(User.__table__.c.telegram_id.type, BigInteger)


def test_daily_usage_has_atomic_uniqueness_key() -> None:
    constraints = DailyUsage.__table__.constraints
    assert any(
        constraint.name == "uq_daily_usage_user_date"
        for constraint in constraints
    )


def test_generation_result_is_one_per_job() -> None:
    column = GenerationResult.__table__.c.job_id
    assert column.unique is True
    assert isinstance(column.type, Uuid)


def test_usage_reservation_is_one_per_job() -> None:
    assert any(
        constraint.name == "uq_usage_reservations_job_id"
        for constraint in UsageReservation.__table__.constraints
    )


def test_generation_dispatch_state_is_durable() -> None:
    columns = GenerationJob.__table__.c.keys()
    assert {"dispatch_attempts", "enqueued_at", "last_dispatch_error"}.issubset(columns)


def test_expected_core_columns_exist() -> None:
    assert {"user_id", "plan_id", "status"}.issubset(
        set(Subscription.__table__.c.keys())
    )
    assert {"plan_id", "duration_days", "status"}.issubset(
        set(ActivationCode.__table__.c.keys())
    )
    assert {"user_id", "plan_id", "provider", "status"}.issubset(
        set(Payment.__table__.c.keys())
    )
    assert {"user_id", "input_type", "status", "progress"}.issubset(
        set(GenerationJob.__table__.c.keys())
    )
    assert {"name", "code", "price", "currency"}.issubset(
        set(Plan.__table__.c.keys())
    )
