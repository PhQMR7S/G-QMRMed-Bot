"""Database-backed runtime settings with stable defaults."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from gqmrmed.db.models import SystemSetting


async def get_runtime_setting(session: AsyncSession, key: str) -> str | None:
    """Return a setting value without creating rows as a side effect."""
    result = await session.execute(select(SystemSetting.value).where(SystemSetting.key == key))
    return result.scalar_one_or_none()


async def set_runtime_setting(session: AsyncSession, *, key: str, value: str) -> SystemSetting:
    """Create or replace a runtime setting atomically within the caller transaction."""
    if not key or len(key) > 128:
        raise ValueError("invalid_setting_key")
    result = await session.execute(
        select(SystemSetting).where(SystemSetting.key == key).with_for_update()
    )
    setting = result.scalar_one_or_none()
    if setting is None:
        setting = SystemSetting(key=key, value=value)
        session.add(setting)
    else:
        setting.value = value
    await session.flush()
    return setting
