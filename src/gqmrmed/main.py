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
