import asyncio

import pytest

import gqmrmed.bot_service as bot_service


@pytest.mark.asyncio
async def test_polling_restarts_after_transient_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = 0
    sleeps: list[float] = []

    async def fake_run_once() -> None:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise RuntimeError("telegram network failure")
        raise asyncio.CancelledError

    async def fake_sleep(delay: float) -> None:
        sleeps.append(delay)

    monkeypatch.setattr(bot_service, "_run_bot_once", fake_run_once)
    monkeypatch.setattr(bot_service.asyncio, "sleep", fake_sleep)

    with pytest.raises(asyncio.CancelledError):
        await bot_service._run_bot_with_lock()

    assert calls == 2
    assert sleeps == [bot_service.POLLING_RESTART_INITIAL_DELAY_SECONDS]
