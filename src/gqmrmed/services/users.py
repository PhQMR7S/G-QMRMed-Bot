"""User provisioning and identity mapping."""

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
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
    """Upsert Telegram profile data without reactivating a blocked user."""
    values = {
        "telegram_id": telegram_id,
        "username": username[:255] if username else None,
        "first_name": first_name[:255] if first_name else None,
        "last_name": last_name[:255] if last_name else None,
        "language": (language or "en")[:16],
        "is_active": True,
    }
    stmt = insert(User).values(**values).on_conflict_do_update(
        index_elements=[User.telegram_id],
        set_={
            "username": values["username"],
            "first_name": values["first_name"],
            "last_name": values["last_name"],
            "language": values["language"],
        },
    ).returning(User.id)
    user_id = (await session.execute(stmt)).scalar_one()
    user = (
        await session.execute(select(User).where(User.id == user_id))
    ).scalar_one()
    return user


async def get_user_by_telegram_id(session: AsyncSession, telegram_id: int) -> User | None:
    """Find a user by Telegram's 64-bit identifier."""
    result = await session.execute(select(User).where(User.telegram_id == telegram_id))
    return result.scalar_one_or_none()
