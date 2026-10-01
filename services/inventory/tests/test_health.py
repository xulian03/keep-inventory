from fastapi.testclient import TestClient
from inventory.main import app


def test_health_ok() -> None:
    with TestClient(app) as client:
        response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"service": "inventory", "status": "ok"}
