"""Standalone Telegram polling runner."""

import asyncio
import logging

from aiogram import Bot, Dispatcher
from redis.asyncio import Redis

from gqmrmed.bot.dispatcher import GenerationDispatcher
from gqmrmed.bot.middleware import DbSessionMiddleware
from gqmrmed.bot.payments import router as payments_router
from gqmrmed.bot.router import router
from gqmrmed.config import get_settings

logger = logging.getLogger(__name__)


async def run_bot() -> None:
    """Start Telegram polling and the durable generation dispatcher."""
    settings = get_settings()
    if not settings.telegram_bot_token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN is required to run the Telegram bot")

    bot = Bot(token=settings.telegram_bot_token)
    dispatcher = Dispatcher()
    session_middleware = DbSessionMiddleware()
    router.message.middleware(session_middleware)
    router.callback_query.middleware(session_middleware)
    payments_router.message.middleware(session_middleware)
    payments_router.callback_query.middleware(session_middleware)
    payments_router.pre_checkout_query.middleware(session_middleware)
    dispatcher.include_router(payments_router)
    dispatcher.include_router(router)

    redis = Redis.from_url(settings.redis_url, decode_responses=True)
    generation_dispatcher = GenerationDispatcher(redis)
    stop_event = asyncio.Event()
    dispatch_task = asyncio.create_task(generation_dispatcher.run(stop_event))

    try:
        await bot.delete_webhook(drop_pending_updates=False)
        await dispatcher.start_polling(bot, handle_signals=False)
    finally:
        stop_event.set()
        await dispatch_task
        await redis.aclose()
        await bot.session.close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(run_bot())
