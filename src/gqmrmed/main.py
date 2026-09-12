from fastapi import FastAPI

from gqmrmed.config import get_settings

settings = get_settings()

app = FastAPI(title=settings.app_name, version=settings.app_version)


@app.get("/health", tags=["system"])
async def health() -> dict[str, str]:
    return {"status": "ok", "service": settings.app_name, "version": settings.app_version}
