from fastapi import APIRouter

from app.api.routes.health import router as health_router
from app.api.routes.system import router as system_router
from app.api.routes.items import router as items_router

api_router = APIRouter(prefix="/api/v1")

api_router.include_router(health_router)
api_router.include_router(system_router)
api_router.include_router(items_router)
