from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_liveness_probe() -> None:
    response = client.get("/api/v1/system/live")

    assert response.status_code == 200
    assert response.json() == {"status": "alive"}


def test_readiness_probe() -> None:
    response = client.get("/api/v1/system/ready")

    assert response.status_code == 200
    assert response.json() == {"status": "ready"}
