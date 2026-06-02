from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_create_organization() -> None:
    response = client.post(
        "/api/v1/organizations/",
        json={"name": "Acme Industries"},
    )

    assert response.status_code == 200

    data = response.json()

    assert data["name"] == "Acme Industries"
    assert "id" in data


def test_get_organizations() -> None:
    response = client.get("/api/v1/organizations/")

    assert response.status_code == 200
    assert isinstance(response.json(), list)
