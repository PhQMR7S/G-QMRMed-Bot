from gqmrmed.db.models import (
    DailyUsage,
    GenerationJob,
    GenerationResult,
    Plan,
    User,
)


def test_telegram_id_uses_64_bit_integer() -> None:
    assert str(User.__table__.c.telegram_id.type) == "BIGINT"


def test_generation_job_supports_non_text_inputs() -> None:
    columns = GenerationJob.__table__.c
    assert "input_storage_key" in columns
    assert "input_mime_type" in columns
    assert "input_metadata" in columns


def test_core_integrity_checks_are_declared() -> None:
    assert {c.name for c in Plan.__table__.constraints if c.name}.issuperset(
        {"ck_plans_price_nonnegative", "ck_plans_duration_positive", "ck_plans_daily_limit_positive"}
    )
    assert any(c.name == "ck_daily_usage_nonnegative" for c in DailyUsage.__table__.constraints)
    assert any(c.name == "ck_generation_progress_range" for c in GenerationJob.__table__.constraints)
    assert any(
        c.name == "ck_generation_dimensions_positive" for c in GenerationResult.__table__.constraints
    )
