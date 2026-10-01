from auth.main import app
from fastapi.testclient import TestClient


def test_health_ok() -> None:
    with TestClient(app) as client:
        response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"service": "auth", "status": "ok"}
