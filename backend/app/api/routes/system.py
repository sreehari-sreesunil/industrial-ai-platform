from fastapi import APIRouter

router = APIRouter(prefix="/system", tags=["system"])


@router.get("/live")
def liveness_probe() -> dict[str, str]:
    return {"status": "alive"}


@router.get("/ready")
def readiness_probe() -> dict[str, str]:
    return {"status": "ready"}
