from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient
from sales import config, rbac


def test_create_and_decode_token_roundtrip() -> None:
    token = rbac.create_access_token(user_id=7, role="admin", name="Ada")
    payload = rbac.decode_token(token)
    assert payload["sub"] == "7"
    assert payload["role"] == "admin"
    assert payload["name"] == "Ada"
    assert "exp" in payload
    assert config.JWT_SECRET


def test_require_roles_with_dummy_app() -> None:
    app = FastAPI()

    @app.get("/solo-admin")
    def solo_admin(user: dict = Depends(rbac.require_roles("admin"))) -> dict:
        return user

    admin_token = rbac.create_access_token(user_id=1, role="admin", name="Ada")
    empleado_token = rbac.create_access_token(user_id=2, role="empleado", name="Eve")

    with TestClient(app) as client:
        response = client.get(
            "/solo-admin", headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 200
        assert response.json() == {"id": 1, "role": "admin", "name": "Ada"}

        response = client.get(
            "/solo-admin", headers={"Authorization": f"Bearer {empleado_token}"}
        )
        assert response.status_code == 403

        response = client.get("/solo-admin")
        assert response.status_code == 401
