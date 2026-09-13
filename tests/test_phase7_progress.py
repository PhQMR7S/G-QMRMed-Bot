"""Phase 7 live Telegram progress presentation tests."""

from gqmrmed.bot.progress import format_progress_message
from gqmrmed.contracts.generation import GenerationStage
from gqmrmed.services.worker import ThrottledProgressReporter


def test_progress_message_contains_stage_progress_and_elapsed() -> None:
    text = format_progress_message(
        GenerationStage.RENDERING,
        70,
        elapsed_seconds=125,
    )

    assert "إخراج التصميم النهائي" in text
    assert "70%" in text
    assert "02:05" in text
    assert "███████" in text


def test_progress_message_validates_progress_bounds() -> None:
    try:
        format_progress_message(GenerationStage.GENERATING, 101)
    except ValueError as exc:
        assert "less than or equal to 100" in str(exc)
    else:
        raise AssertionError("out-of-range progress was accepted")


def test_progress_reporter_forces_first_stage_update() -> None:
    reporter = ThrottledProgressReporter(interval_seconds=4.0)
    assert reporter.should_emit(GenerationStage.RESEARCHING, 1)
    assert not reporter.should_emit(GenerationStage.RESEARCHING, 2)
