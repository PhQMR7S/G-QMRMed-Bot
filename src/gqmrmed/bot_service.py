"""Render-compatible Telegram polling service with a lightweight HTTP health port."""

from __future__ import annotations

import asyncio
import logging
import os

import uvicorn
from fastapi import FastAPI

from gqmrmed.bot.runner import run_bot
from gqmrmed.config import get_settings

logging.basicConfig(level=get_settings().log_level)
logger = logging.getLogger(__name__)

app = FastAPI(title="GQMRMed Telegram Bot Service")
_bot_task: asyncio.Task[None] | None = None


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": "telegram-bot"}


@app.on_event("startup")
async def startup() -> None:
    global _bot_task
    _bot_task = asyncio.create_task(run_bot())

    def report_failure(task: asyncio.Task[None]) -> None:
        if task.cancelled():
            return
        exc = task.exception()
        if exc is not None:
            logger.error("telegram_bot_service_failed: %s", exc)

    _bot_task.add_done_callback(report_failure)
    logger.info("telegram_bot_service_started")


@app.on_event("shutdown")
async def shutdown() -> None:
    global _bot_task
    if _bot_task is not None and not _bot_task.done():
        _bot_task.cancel()
        try:
            await _bot_task
        except asyncio.CancelledError:
            pass
    _bot_task = None


if __name__ == "__main__":
    uvicorn.run(
        "gqmrmed.bot_service:app",
        host="0.0.0.0",
        port=int(os.environ.get("PORT", "10000")),
    )
