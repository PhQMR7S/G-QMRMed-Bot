"""User provisioning and identity mapping."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from gqmrmed.db.models import User


async def get_or_create_user(
    session: AsyncSession,
    *,
    telegram_id: int,
    username: str | None,
    first_name: str | None,
    last_name: str | None,
    language: str | None,
) -> User:
    """Return the Telegram user, updating mutable profile fields safely."""
    result = await session.execute(select(User).where(User.telegram_id == telegram_id))
    user = result.scalar_one_or_none()
    if user is None:
        user = User(
            telegram_id=telegram_id,
            username=username,
            first_name=first_name,
            last_name=last_name,
            language=(language or "en")[:16],
        )
        session.add(user)
        await session.flush()
        return user

    user.username = username
    user.first_name = first_name
    user.last_name = last_name
    if language:
        user.language = language[:16]
    user.is_active = True
    await session.flush()
    return user


async def get_user_by_telegram_id(session: AsyncSession, telegram_id: int) -> User | None:
    """Find a user by Telegram's 64-bit identifier."""
    result = await session.execute(select(User).where(User.telegram_id == telegram_id))
    return result.scalar_one_or_none()


def user_uuid(user: User) -> UUID:
    """Return the internal UUID used by application services."""
    return user.id
