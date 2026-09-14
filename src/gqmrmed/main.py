import asyncio
import contextlib
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from aiogram import Bot
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from redis.asyncio import Redis
from sqlalchemy import text

from gqmrmed.admin import router as admin_router
from gqmrmed.admin_panel import router as admin_panel_router
from gqmrmed.admin_plans import router as admin_plans_router
from gqmrmed.config import get_settings
from gqmrmed.db.session import SessionFactory

settings = get_settings()
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Manage the optional embedded worker for the complete API lifespan."""
    app.state.worker_task = None
    app.state.worker_stop = None
    app.state.worker_bot = None

    if settings.service_role == "api" and settings.run_worker_in_api:
        if not settings.telegram_bot_token:
            logger.warning("Embedded worker disabled: TELEGRAM_BOT_TOKEN is not configured")
        else:
            try:
                from gqmrmed.services.runtime import build_worker

                bot = Bot(token=settings.telegram_bot_token)
                worker = build_worker(settings, bot)
                stop_event = asyncio.Event()
                app.state.worker_bot = bot
                app.state.worker_stop = stop_event
                app.state.worker_task = asyncio.create_task(worker.run(stop_event))
                logger.info("Embedded generation worker started")
            except Exception as exc:
                logger.exception(
                    "Embedded worker configuration failed; API will remain available",
                    extra={"reason": str(exc)},
                )

    try:
        yield
    finally:
        stop_event_for_shutdown: asyncio.Event | None = getattr(
            app.state, "worker_stop", None
        )
        worker_task = getattr(app.state, "worker_task", None)
        bot_for_shutdown: Bot | None = getattr(app.state, "worker_bot", None)
        if stop_event_for_shutdown is not None:
            stop_event_for_shutdown.set()
        if worker_task is not None:
            with contextlib.suppress(asyncio.CancelledError):
                await worker_task
        if bot_for_shutdown is not None:
            await bot_for_shutdown.session.close()


app = FastAPI(title=settings.app_name, version=settings.app_version, lifespan=lifespan)
app.include_router(admin_router)
app.include_router(admin_panel_router)
app.include_router(admin_plans_router)


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
