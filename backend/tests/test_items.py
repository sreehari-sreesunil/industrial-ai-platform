from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_create_item() -> None:
    response = client.post("/api/v1/items/", json={"name": "Industrial Sensor"})

    assert response.status_code == 200

    data = response.json()

    assert data["name"] == "Industrial Sensor"
    assert "id" in data
