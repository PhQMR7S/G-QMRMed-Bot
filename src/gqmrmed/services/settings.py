"""Database-backed runtime settings with stable defaults."""

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from gqmrmed.db.models import SystemSetting


async def get_runtime_setting(session: AsyncSession, key: str) -> str | None:
    """Return a string setting value without creating rows as a side effect."""
    result = await session.execute(select(SystemSetting.value).where(SystemSetting.key == key))
    value = result.scalar_one_or_none()
    return value if isinstance(value, str) else None


async def set_runtime_setting(session: AsyncSession, *, key: str, value: str) -> SystemSetting:
    """Create or replace a runtime setting atomically within the caller transaction."""
    if not key or len(key) > 128:
        raise ValueError("invalid_setting_key")
    stmt = insert(SystemSetting).values(key=key, value=value).on_conflict_do_update(
        index_elements=[SystemSetting.key],
        set_={"value": value},
    ).returning(SystemSetting.id)
    setting_id = (await session.execute(stmt)).scalar_one()
    setting = (
        await session.execute(select(SystemSetting).where(SystemSetting.id == setting_id))
    ).scalar_one()
    return setting
