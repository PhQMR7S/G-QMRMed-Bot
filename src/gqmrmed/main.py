import asyncio
import contextlib

from aiogram import Bot
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from redis.asyncio import Redis
from sqlalchemy import text

from gqmrmed.admin import router as admin_router
from gqmrmed.admin_panel import router as admin_panel_router
from gqmrmed.config import get_settings
from gqmrmed.db.session import SessionFactory

settings = get_settings()

app = FastAPI(title=settings.app_name, version=settings.app_version)
app.include_router(admin_router)
app.include_router(admin_panel_router)


@app.on_event("startup")
async def start_embedded_worker() -> None:
    """Run the durable generation worker in the free API instance when enabled."""
    if settings.service_role != "api" or not settings.run_worker_in_api:
        app.state.worker_task = None
        app.state.worker_stop = None
        app.state.worker_bot = None
        return

    if not settings.telegram_bot_token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN is required when RUN_WORKER_IN_API=true")

    from gqmrmed.services.runtime import build_worker

    bot = Bot(token=settings.telegram_bot_token)
    worker = build_worker(settings, bot)
    stop_event = asyncio.Event()
    app.state.worker_bot = bot
    app.state.worker_stop = stop_event
    app.state.worker_task = asyncio.create_task(worker.run(stop_event))


@app.on_event("shutdown")
async def stop_embedded_worker() -> None:
    stop_event = getattr(app.state, "worker_stop", None)
    worker_task = getattr(app.state, "worker_task", None)
    bot = getattr(app.state, "worker_bot", None)
    if stop_event is not None:
        stop_event.set()
    if worker_task is not None:
        with contextlib.suppress(asyncio.CancelledError):
            await worker_task
    if bot is not None:
        await bot.session.close()


@app.get("/health", tags=["system"])
async def health() -> dict[str, str]:
    """Lightweight liveness endpoint that never depends on external services."""
    return {"status": "ok", "service": settings.app_name, "version": settings.app_version}


@app.get("/health/live", tags=["system"])
async def health_live() -> dict[str, str]:
    """Explicit liveness endpoint for container orchestration."""
    return {"status": "ok"}


@app.get("/health/ready", tags=["system"], response_model=None)
async def health_ready() -> JSONResponse:
    """Check the dependencies required before accepting generation work."""
    checks: dict[str, str] = {}

    try:
        async with SessionFactory() as session:
            await session.execute(text("SELECT 1"))
        checks["database"] = "ok"
    except Exception:
        checks["database"] = "error"

    redis = Redis.from_url(settings.redis_url)
    try:
        await redis.ping()
        checks["redis"] = "ok"
    except Exception:
        checks["redis"] = "error"
    finally:
        await redis.aclose()

    if all(value == "ok" for value in checks.values()):
        return JSONResponse(content={"status": "ready", **checks})
    return JSONResponse(status_code=503, content={"status": "not_ready", **checks})
