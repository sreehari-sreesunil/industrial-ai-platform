from fastapi import APIRouter

from app.api.routes.health import router as health_router
from app.api.routes.system import router as system_router
from app.api.routes.items import router as items_router
from app.api.routes.organizations import (
    router as organizations_router,
)
from app.api.routes.facilities import (
    router as facilities_router,
)
from app.api.routes.asset_types import (
    router as asset_types_router,
)
from app.api.routes.assets import (
    router as assets_router,
)
from app.api.routes.telemetry import (
    router as telemetry_router,
)
from app.api.routes.metric_definitions import (
    router as metric_definitions_router,
)


api_router = APIRouter(prefix="/api/v1")

api_router.include_router(health_router)
api_router.include_router(system_router)
api_router.include_router(items_router)
api_router.include_router(organizations_router)
api_router.include_router(facilities_router)
api_router.include_router(asset_types_router)
api_router.include_router(assets_router)
api_router.include_router(telemetry_router)
api_router.include_router(metric_definitions_router)
