import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from sqlalchemy import text
from app.db.session import engine

from app.api.main import api_router
from app.core.config import settings
from app.core.logging import setup_logging

logger = logging.getLogger(__name__)

with engine.connect() as connection:
    connection.execute(text("SELECT 1"))

logger.info("Database connection established")


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
