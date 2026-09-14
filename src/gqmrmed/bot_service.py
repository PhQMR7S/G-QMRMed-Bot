"""Render-compatible Telegram polling service with a lightweight HTTP health port."""

from __future__ import annotations

import asyncio
import logging
import os
import uuid
from collections.abc import Awaitable
from typing import Any, cast

import uvicorn
from fastapi import FastAPI
from redis.asyncio import Redis

from gqmrmed.bot.runner import run_bot
from gqmrmed.config import get_settings

logging.basicConfig(level=get_settings().log_level)
logger = logging.getLogger(__name__)

app = FastAPI(title="GQMRMed Telegram Bot Service")
_bot_task: asyncio.Task[None] | None = None

POLLING_LOCK_KEY = "gqmrmed:telegram:polling-lock:v2"
POLLING_LOCK_TTL_SECONDS = 60
POLLING_LOCK_HEARTBEAT_SECONDS = 15


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": "telegram-bot"}


async def _release_lock(redis: Redis, token: str) -> None:
    await cast(
        Awaitable[Any],
        redis.eval(
            """
            if redis.call('get', KEYS[1]) == ARGV[1] then
                return redis.call('del', KEYS[1])
            end
            return 0
            """,
            1,
            POLLING_LOCK_KEY,
            token,
        ),
    )


async def _heartbeat(redis: Redis, token: str, stop_event: asyncio.Event) -> None:
    while not stop_event.is_set():
        try:
            await asyncio.wait_for(
                stop_event.wait(), timeout=POLLING_LOCK_HEARTBEAT_SECONDS
            )
            return
        except TimeoutError:
            pass

        refreshed = await cast(
            Awaitable[Any],
            redis.eval(
                """
                if redis.call('get', KEYS[1]) == ARGV[1] then
                    return redis.call('expire', KEYS[1], ARGV[2])
                end
                return 0
                """,
                1,
                POLLING_LOCK_KEY,
                token,
                str(POLLING_LOCK_TTL_SECONDS),
            ),
        )
        if not refreshed:
            raise RuntimeError("Telegram polling lock was lost")


async def _acquire_polling_lock(redis: Redis, token: str) -> None:
    while True:
        acquired = await redis.set(
            POLLING_LOCK_KEY,
            token,
            nx=True,
            ex=POLLING_LOCK_TTL_SECONDS,
        )
        if acquired:
            return
        logger.warning("telegram_polling_lock_busy; waiting for active instance")
        await asyncio.sleep(5)


async def _run_bot_with_lock() -> None:
    settings = get_settings()
    if not settings.telegram_bot_token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN is required to run the Telegram bot")
    if not settings.redis_url:
        raise RuntimeError("REDIS_URL is required to coordinate Telegram polling")

    redis = Redis.from_url(settings.redis_url, decode_responses=True)
    token = uuid.uuid4().hex
    lock_stop = asyncio.Event()
    heartbeat_task: asyncio.Task[None] | None = None
    bot_task: asyncio.Task[None] | None = None

    try:
        await _acquire_polling_lock(redis, token)
        logger.info("telegram_polling_lock_acquired")
        heartbeat_task = asyncio.create_task(_heartbeat(redis, token, lock_stop))
        bot_task = asyncio.create_task(run_bot())

        done, _ = await asyncio.wait(
            {bot_task, heartbeat_task},
            return_when=asyncio.FIRST_EXCEPTION,
        )
        for task in done:
            exception = task.exception()
            if exception is not None:
                raise exception
        await bot_task
    finally:
        lock_stop.set()
        if heartbeat_task is not None and not heartbeat_task.done():
            heartbeat_task.cancel()
            try:
                await heartbeat_task
            except asyncio.CancelledError:
                pass
        if bot_task is not None and not bot_task.done():
            bot_task.cancel()
            try:
                await bot_task
            except asyncio.CancelledError:
                pass
        try:
            await _release_lock(redis, token)
        finally:
            logger.info("telegram_polling_lock_released")
            await redis.aclose()


@app.on_event("startup")
async def startup() -> None:
    global _bot_task
    _bot_task = asyncio.create_task(_run_bot_with_lock())

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
