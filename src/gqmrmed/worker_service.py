"""Render-compatible generation worker service with a lightweight HTTP health port."""

from __future__ import annotations

import asyncio
import contextlib
import logging
import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import uvicorn
from aiogram import Bot
from fastapi import FastAPI

from gqmrmed.config import get_settings
from gqmrmed.db.migrations import upgrade_head

logging.basicConfig(level=get_settings().log_level)
logger = logging.getLogger(__name__)

_worker_task: asyncio.Task[None] | None = None
_bot: Bot | None = None
_stop_event: asyncio.Event | None = None


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Start the worker task without blocking Render's health port."""
    global _worker_task
    _worker_task = asyncio.create_task(_run())

    def report_failure(task: asyncio.Task[None]) -> None:
        if task.cancelled():
            return
        exc = task.exception()
        if exc is not None:
            logger.error("generation_worker_service_failed: %s", exc)

    _worker_task.add_done_callback(report_failure)
    try:
        yield
    finally:
        if _stop_event is not None:
            _stop_event.set()
        if _worker_task is not None and not _worker_task.done():
            with contextlib.suppress(asyncio.CancelledError):
                await _worker_task
        _worker_task = None


app = FastAPI(title="GQMRMed Generation Worker Service", lifespan=lifespan)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": "generation-worker"}


async def _run() -> None:
    global _bot, _stop_event
    settings = get_settings()
    if not settings.telegram_bot_token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN is required to run the generation worker")

    logger.info("database_migration_starting")
    await upgrade_head()
    logger.info("database_migration_complete")

    from gqmrmed.services.runtime import build_worker

    _bot = Bot(token=settings.telegram_bot_token)
    worker = build_worker(settings, _bot)
    _stop_event = asyncio.Event()
    try:
        logger.info("generation_worker_service_started")
        await worker.run(_stop_event)
    finally:
        await _bot.session.close()
        _bot = None
        _stop_event = None


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "10000"))
    uvicorn.run("gqmrmed.worker_service:app", host="0.0.0.0", port=port)
