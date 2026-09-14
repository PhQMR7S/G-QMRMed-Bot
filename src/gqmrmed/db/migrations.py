"""Run Alembic migrations safely before services start using the database."""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from gqmrmed.config import get_settings

_MIGRATION_LOCK_SQL = "SELECT pg_advisory_lock(hashtext('gqmrmed:alembic'))"
_MIGRATION_UNLOCK_SQL = "SELECT pg_advisory_unlock(hashtext('gqmrmed:alembic'))"


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


async def upgrade_head() -> None:
    """Upgrade the database to Alembic head, serializing concurrent services."""
    settings = get_settings()
    engine = create_async_engine(settings.database_url, pool_pre_ping=True)
    async with engine.connect() as connection:
        await connection.execute(text(_MIGRATION_LOCK_SQL))
        await connection.commit()
        try:
            process = await asyncio.create_subprocess_exec(
                sys.executable,
                "-m",
                "alembic",
                "upgrade",
                "head",
                cwd=_repo_root(),
                env=os.environ.copy(),
            )
            return_code = await process.wait()
            if return_code != 0:
                raise RuntimeError(f"database_migration_failed:{return_code}")
        finally:
            await connection.execute(text(_MIGRATION_UNLOCK_SQL))
            await connection.commit()
    await engine.dispose()


__all__ = ["upgrade_head"]
