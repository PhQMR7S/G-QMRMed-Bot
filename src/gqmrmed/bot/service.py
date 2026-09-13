"""Application services used by Telegram handlers."""

from dataclasses import dataclass
from datetime import date, datetime, UTC
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from gqmrmed.contracts.generation import GenerationRequest, InputType
from gqmrmed.db.models import User
from gqmrmed.services.entitlements import Entitlement, resolve_entitlement
from gqmrmed.services.jobs import create_generation_job
from gqmrmed.services.usage import QuotaExceededError, Reservation, reserve_generation
from gqmrmed.services.users import get_or_create_user


@dataclass(frozen=True, slots=True)
class EnqueuedGeneration:
    """Database-side generation request awaiting durable queue dispatch."""

    job_id: UUID
    reservation: Reservation
    entitlement: Entitlement


async def provision_user(
    session: AsyncSession,
    *,
    telegram_id: int,
    username: str | None,
    first_name: str | None,
    last_name: str | None,
    language: str | None,
) -> User:
    """Create/update a Telegram user without changing moderation state."""
    return await get_or_create_user(
        session,
        telegram_id=telegram_id,
        username=username,
        first_name=first_name,
        last_name=last_name,
        language=language,
    )


async def create_user_generation(
    session: AsyncSession,
    *,
    user: User,
    request: GenerationRequest,
    telegram_chat_id: int | None = None,
    usage_date: date | None = None,
) -> EnqueuedGeneration:
    """Atomically create a job and reserve exactly one usage slot."""
    if not user.is_active:
        raise PermissionError("user_inactive")
    if telegram_chat_id is not None and telegram_chat_id <= 0:
        raise ValueError("invalid_telegram_chat_id")

    entitlement = await resolve_entitlement(session, user_id=user.id)
    metadata = dict(request.metadata or {})
    if telegram_chat_id is not None:
        metadata["telegram_chat_id"] = telegram_chat_id
    job = await create_generation_job(
        session,
        user_id=user.id,
        input_type=request.input_type.value,
        input_text=request.text,
        input_storage_key=request.storage_key,
        input_mime_type=request.mime_type,
        input_metadata=metadata or None,
    )
    reservation = await reserve_generation(
        session,
        user_id=user.id,
        job_id=job.id,
        usage_date=usage_date or datetime.now(UTC).date(),
        daily_limit=entitlement.daily_limit,
    )
    return EnqueuedGeneration(
        job_id=job.id,
        reservation=reservation,
        entitlement=entitlement,
    )


__all__ = [
    "EnqueuedGeneration",
    "InputType",
    "QuotaExceededError",
    "create_user_generation",
    "provision_user",
]
