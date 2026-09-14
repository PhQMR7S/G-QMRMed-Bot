"""Render-compatible generation worker service with a lightweight HTTP health port."""

from __future__ import annotations

import asyncio
import logging
import os

import uvicorn
from aiogram import Bot
from fastapi import FastAPI

from gqmrmed.config import get_settings

logging.basicConfig(level=get_settings().log_level)
logger = logging.getLogger(__name__)

app = FastAPI(title="GQMRMed Generation Worker Service")
_worker_task: asyncio.Task[None] | None = None
_bot: Bot | None = None
_stop_event: asyncio.Event | None = None


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": "generation-worker"}


async def _run() -> None:
    global _bot, _stop_event
    settings = get_settings()
    if not settings.telegram_bot_token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN is required to run the generation worker")

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


@app.on_event("startup")
async def startup() -> None:
    global _worker_task
    _worker_task = asyncio.create_task(_run())

    def report_failure(task: asyncio.Task[None]) -> None:
        if task.cancelled():
            return
        exc = task.exception()
        if exc is not None:
            logger.error("generation_worker_service_failed: %s", exc)

    _worker_task.add_done_callback(report_failure)


@app.on_event("shutdown")
async def shutdown() -> None:
    global _worker_task
    if _stop_event is not None:
        _stop_event.set()
    if _worker_task is not None and not _worker_task.done():
        await _worker_task
    _worker_task = None


if __name__ == "__main__":
    uvicorn.run(
        "gqmrmed.worker_service:app",
        host="0.0.0.0",
        port=int(os.environ.get("PORT", "10000")),
    )
