from fastapi import FastAPI

from app.core.config import settings

app = FastAPI(
    title = settings.app_name,
    version = settings.app_version
)


@app.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "ok"}

@app.get("/info")
def app_info() -> dict[str, str]:
    return {
        "app_name" : settings.app_name,
        "version" : settings.app_version,
        "environment" : settings.environment
    }
