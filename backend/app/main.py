import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.main import api_router
from app.core.config import settings
from app.core.logging import setup_logging

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    setup_logging()

    logger.info("Application starting up")

    yield

    logger.info("Application shutting down")


app = FastAPI(title=settings.app_name, version=settings.app_version, lifespan=lifespan)

app.include_router(api_router)


@app.get("/info")
def app_info() -> dict[str, str]:
    return {
        "app_name": settings.app_name,
        "version": settings.app_version,
        "environment": settings.environment,
    }
