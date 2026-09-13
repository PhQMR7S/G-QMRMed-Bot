import asyncio

import uvicorn
from aiogram import Bot

from gqmrmed.config import get_settings


async def _run_worker() -> None:
    """Run the durable generation worker as an independent service."""
    from gqmrmed.services.runtime import build_worker

    settings = get_settings()
    if not settings.telegram_bot_token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN is required to run the generation worker")
    bot = Bot(token=settings.telegram_bot_token)
    worker = build_worker(settings, bot)
    stop_event = asyncio.Event()
    try:
        await worker.run(stop_event)
    finally:
        await bot.session.close()


if __name__ == "__main__":
    settings = get_settings()
    if settings.service_role == "bot":
        from gqmrmed.bot.runner import run_bot

        asyncio.run(run_bot())
    elif settings.service_role == "worker":
        asyncio.run(_run_worker())
    elif settings.service_role == "api":
        uvicorn.run(
            "gqmrmed.main:app",
            host="0.0.0.0",
            port=8000,
            reload=settings.app_env == "development",
        )
    else:
        raise RuntimeError("SERVICE_ROLE must be 'api', 'bot', or 'worker'")
