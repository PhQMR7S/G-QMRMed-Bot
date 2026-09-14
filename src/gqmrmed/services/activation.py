"""Secure generation of single-use subscription activation codes."""

from datetime import datetime
from secrets import choice

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from gqmrmed.db.models import ActivationCode, Plan
from gqmrmed.services.subscriptions import hash_activation_code

_ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"


def generate_activation_code(plan_code: str, *, group_length: int = 6) -> str:
    """Generate a human-enterable code; only its hash is persisted."""
    if not 4 <= group_length <= 8:
        raise ValueError("invalid_code_group_length")
    prefix = plan_code.strip().upper()
    if not prefix or len(prefix) > 16 or not prefix.replace("_", "").isalnum():
        raise ValueError("invalid_plan_code")
    groups = ["".join(choice(_ALPHABET) for _ in range(group_length)) for _ in range(2)]
    return f"GQMR-{prefix}-{'-'.join(groups)}"


async def create_activation_code(
    session: AsyncSession,
    *,
    plan: Plan,
    duration_days: int,
    expires_at: datetime | None = None,
) -> tuple[ActivationCode, str]:
    """Create a unique hashed activation code and return plaintext once."""
    if duration_days <= 0:
        raise ValueError("invalid_subscription_duration")
    for _ in range(10):
        plaintext = generate_activation_code(plan.code)
        code_hash = hash_activation_code(plaintext)
        stmt = (
            insert(ActivationCode)
            .values(
                code_hash=code_hash,
                plan_id=plan.id,
                duration_days=duration_days,
                expires_at=expires_at,
            )
            .on_conflict_do_nothing(index_elements=[ActivationCode.code_hash])
            .returning(ActivationCode.id)
        )
        async with session.begin_nested():
            result = await session.execute(stmt)
            code_id = result.scalar_one_or_none()
        if code_id is not None:
            code = await session.get(ActivationCode, code_id)
            if code is None:
                raise RuntimeError("activation_code_persistence_failed")
            return code, plaintext
    raise RuntimeError("activation_code_generation_collision")
