from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_create_item() -> None:
    response = client.post("/api/v1/items/", json={"name": "Industrial Sensor"})

    assert response.status_code == 200

    data = response.json()

    assert data["name"] == "Industrial Sensor"
    assert "id" in data


def test_get_items() -> None:
    response = client.get("/api/v1/items/")

    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_get_single_item() -> None:
    create_response = client.post(
        "/api/v1/items/",
        json={"name": "Pressure Sensor"},
    )

    item_id = create_response.json()["id"]

    response = client.get(f"/api/v1/items/{item_id}")

    assert response.status_code == 200

    data = response.json()

    assert data["id"] == item_id
    assert data["name"] == "Pressure Sensor"


def test_get_missing_item() -> None:
    response = client.get("/api/v1/items/999999")

    assert response.status_code == 404
    assert response.json()["detail"] == "Item not found"
