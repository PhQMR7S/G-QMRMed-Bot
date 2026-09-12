import uvicorn

from gqmrmed.config import get_settings

if __name__ == "__main__":
    settings = get_settings()
    uvicorn.run(
        "gqmrmed.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.app_env == "development",
    )
