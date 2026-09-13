from datetime import datetime, timedelta, UTC
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

import pytest

from gqmrmed.db.models import PlanCode, SubscriptionStatus
from gqmrmed.services.subscriptions import grant_paid_subscription


class Result:
    def __init__(self, value: object) -> None:
        self.value = value

    def scalar_one_or_none(self) -> object:
        return self.value

    def all(self) -> list[object]:
        return self.value if isinstance(self.value, list) else []


class Session:
    def __init__(self, *values: object) -> None:
        self.values = list(values)
        self.index = 0
        self.added: list[object] = []

    async def execute(self, _statement: object) -> Result:
        value = self.values[self.index]
        self.index += 1
        return Result(value)

    def add(self, value: object) -> None:
        self.added.append(value)

    async def flush(self) -> None:
        return None


def plan(code: PlanCode, price: str, days: int, limit: int) -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid4(),
        code=code.value,
        price=Decimal(price),
        duration_days=days,
        daily_limit=limit,
        is_active=True,
    )


@pytest.mark.asyncio
async def test_first_paid_grant_starts_now() -> None:
    plus = plan(PlanCode.PLUS, "5", 30, 8)
    user = SimpleNamespace(id=uuid4())
    session = Session(user, [])

    subscription = await grant_paid_subscription(session, user_id=user.id, plan=plus)

    assert subscription.starts_at is not None
    assert subscription.expires_at is not None
    assert subscription.expires_at > subscription.starts_at
    assert len(session.added) == 1


@pytest.mark.asyncio
async def test_same_plan_purchase_extends_from_current_expiry() -> None:
    plus = plan(PlanCode.PLUS, "5", 30, 8)
    user = SimpleNamespace(id=uuid4())
    expiry = datetime.now(UTC) + timedelta(days=10)
    current = SimpleNamespace(
        id=uuid4(),
        user_id=user.id,
        plan_id=plus.id,
        status=SubscriptionStatus.ACTIVE.value,
        starts_at=expiry - timedelta(days=20),
        expires_at=expiry,
    )
    session = Session(user, [(current, plus)])

    subscription = await grant_paid_subscription(session, user_id=user.id, plan=plus)

    assert subscription.starts_at == expiry
    assert subscription.expires_at == expiry + timedelta(days=30)
    assert current.status == SubscriptionStatus.ACTIVE.value


@pytest.mark.asyncio
async def test_upgrade_is_immediate_and_preserves_remaining_value() -> None:
    plus = plan(PlanCode.PLUS, "5", 30, 8)
    pro = plan(PlanCode.PRO, "20", 90, 15)
    user = SimpleNamespace(id=uuid4())
    expiry = datetime.now(UTC) + timedelta(days=15)
    current = SimpleNamespace(
        id=uuid4(),
        user_id=user.id,
        plan_id=plus.id,
        status=SubscriptionStatus.ACTIVE.value,
        starts_at=expiry - timedelta(days=15),
        expires_at=expiry,
    )
    session = Session(user, [(current, plus)])

    subscription = await grant_paid_subscription(session, user_id=user.id, plan=pro)

    assert subscription.starts_at is not None
    assert subscription.starts_at <= datetime.now(UTC)
    assert subscription.expires_at > subscription.starts_at + timedelta(days=90)
    assert current.status == SubscriptionStatus.CANCELLED.value


@pytest.mark.asyncio
async def test_downgrade_is_queued_after_current_entitlement() -> None:
    plus = plan(PlanCode.PLUS, "5", 30, 8)
    pro = plan(PlanCode.PRO, "20", 90, 15)
    user = SimpleNamespace(id=uuid4())
    expiry = datetime.now(UTC) + timedelta(days=20)
    current = SimpleNamespace(
        id=uuid4(),
        user_id=user.id,
        plan_id=pro.id,
        status=SubscriptionStatus.ACTIVE.value,
        starts_at=expiry - timedelta(days=70),
        expires_at=expiry,
    )
    session = Session(user, [(current, pro)])

    subscription = await grant_paid_subscription(session, user_id=user.id, plan=plus)

    assert subscription.starts_at == expiry
    assert subscription.expires_at == expiry + timedelta(days=30)
    assert current.status == SubscriptionStatus.ACTIVE.value
