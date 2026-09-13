from datetime import date
from types import SimpleNamespace
from uuid import uuid4

import pytest

from gqmrmed.services.usage import reserve_generation


class Result:
    def __init__(self, value: object) -> None:
        self.value = value

    def scalar_one_or_none(self) -> object:
        return self.value


class Session:
    def __init__(self, *values: object) -> None:
        self.values = list(values)
        self.index = 0

    async def execute(self, _statement: object) -> Result:
        value = self.values[self.index]
        self.index += 1
        return Result(value)

    async def flush(self) -> None:
        return None


@pytest.mark.asyncio
async def test_duplicate_job_returns_existing_reservation_without_quota_write() -> None:
    user_id = uuid4()
    job_id = uuid4()
    reservation_id = uuid4()
    existing = SimpleNamespace(
        id=reservation_id,
        user_id=user_id,
        job_id=job_id,
        usage_date=date(2026, 9, 13),
    )
    session = Session(None, existing)

    result = await reserve_generation(
        session,
        user_id=user_id,
        job_id=job_id,
        usage_date=date(2026, 9, 13),
        daily_limit=3,
    )

    assert result.id == reservation_id
    assert result.job_id == job_id
    assert session.index == 2
