"""Phase 6 worker progress and durable result pipeline tests."""

import pytest

from gqmrmed.contracts.generation import GenerationStage
from gqmrmed.services.worker import ThrottledProgressReporter


def test_progress_reporter_emits_first_update() -> None:
    reporter = ThrottledProgressReporter(interval_seconds=4.0)
    assert reporter.should_emit(GenerationStage.RESEARCHING, 1)


def test_progress_reporter_suppresses_redundant_fast_updates() -> None:
    reporter = ThrottledProgressReporter(interval_seconds=4.0)
    assert reporter.should_emit(GenerationStage.RESEARCHING, 1)
    assert not reporter.should_emit(GenerationStage.RESEARCHING, 2)


def test_progress_reporter_emits_stage_change() -> None:
    reporter = ThrottledProgressReporter(interval_seconds=4.0)
    reporter.should_emit(GenerationStage.RESEARCHING, 1)
    assert reporter.should_emit(GenerationStage.SYNTHESIZING, 10)


def test_progress_reporter_rejects_too_frequent_interval() -> None:
    with pytest.raises(ValueError, match="progress_interval_too_short"):
        ThrottledProgressReporter(interval_seconds=0.5)
