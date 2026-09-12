import asyncio

import uvicorn

from gqmrmed.config import get_settings

if __name__ == "__main__":
    settings = get_settings()
    if settings.service_role == "bot":
        from gqmrmed.bot.runner import run_bot

        asyncio.run(run_bot())
    elif settings.service_role == "api":
        uvicorn.run(
            "gqmrmed.main:app",
            host="0.0.0.0",
            port=8000,
            reload=settings.app_env == "development",
        )
    else:
        raise RuntimeError("SERVICE_ROLE must be 'api' or 'bot'")
