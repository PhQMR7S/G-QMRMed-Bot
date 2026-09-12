"""Secure generation of single-use subscription activation codes."""

from datetime import datetime
from secrets import choice
from string import ascii_uppercase, digits
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from gqmrmed.db.models import ActivationCode, Plan
from gqmrmed.services.subscriptions import hash_activation_code


_ALPHABET = ascii_uppercase + digits


def generate_activation_code(plan_code: str, *, group_length: int = 4) -> str:
    """Generate a human-enterable code; only its hash is persisted."""
    if not 2 <= group_length <= 8:
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
    created_by: UUID | None,
    expires_at: datetime | None = None,
) -> tuple[ActivationCode, str]:
    """Create a unique hashed activation code and return plaintext once."""
    if duration_days <= 0:
        raise ValueError("invalid_subscription_duration")
    for _ in range(10):
        plaintext = generate_activation_code(plan.code)
        code_hash = hash_activation_code(plaintext)
        try:
            async with session.begin_nested():
                code = ActivationCode(
                    code_hash=code_hash,
                    plan_id=plan.id,
                    duration_days=duration_days,
                    created_by=created_by,
                    expires_at=expires_at,
                )
                session.add(code)
                await session.flush()
            return code, plaintext
        except IntegrityError:
            continue
    raise RuntimeError("activation_code_generation_collision")
