"""Tests del servicio auth (F-003, paso 5).

Cada test apunta AUTH_DB a un SQLite temporal (via monkeypatch) y siembra dos
usuarios; la app real se usa con TestClient para login y /auth/me. El RBAC se
prueba sobre una app dummy para no anadir rutas a la app real.
"""

from datetime import datetime, timedelta, timezone

import jwt
import pytest
from auth import config, db, security
from auth.main import app as auth_app
from auth.models import Base, User
from auth.rbac import create_access_token, require_roles
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

_ADMIN_EMAIL = "admin@tienda.com"
_ADMIN_PASSWORD = "admin123"
_EMPLEADO_EMAIL = "empleado@tienda.com"
_EMPLEADO_PASSWORD = "empleado123"


@pytest.fixture
def seeded_db(tmp_path, monkeypatch):
    """Crea una BD temporal con admin y empleado y devuelve sus ids."""
    db_path = tmp_path / "auth_test.db"
    monkeypatch.setenv("AUTH_DB", str(db_path))

    engine = db.get_engine()
    Base.metadata.create_all(engine)

    session = db.get_session_factory(engine)()
    admin = User(
        name="Admin",
        email=_ADMIN_EMAIL,
        password_hash=security.hash_password(_ADMIN_PASSWORD),
        role="admin",
        created_at="2026-10-01T00:00:00",
    )
    empleado = User(
        name="Empleado",
        email=_EMPLEADO_EMAIL,
        password_hash=security.hash_password(_EMPLEADO_PASSWORD),
        role="empleado",
        created_at="2026-10-01T00:00:00",
    )
    session.add_all([admin, empleado])
    session.commit()
    ids = {"admin": admin.id, "empleado": empleado.id}
    session.close()
    engine.dispose()
    return ids


def _login(client, email, password):
    return client.post("/auth/login", json={"email": email, "password": password})


def _dummy_rbac_app() -> FastAPI:
    app = FastAPI()

    @app.get("/admin-only")
    def admin_only(user: dict = Depends(require_roles("admin"))) -> dict:
        return user

    return app


def test_login_ok_devuelve_token_y_claims(seeded_db):
    with TestClient(auth_app) as client:
        response = _login(client, _ADMIN_EMAIL, _ADMIN_PASSWORD)

    assert response.status_code == 200
    body = response.json()
    assert body["user"] == {
        "id": seeded_db["admin"],
        "name": "Admin",
        "email": _ADMIN_EMAIL,
        "role": "admin",
    }

    payload = jwt.decode(body["token"], config.JWT_SECRET, algorithms=["HS256"])
    assert payload["sub"] == str(seeded_db["admin"])
    assert payload["role"] == "admin"
    assert payload["name"] == "Admin"
    expected_exp = datetime.now(timezone.utc) + timedelta(hours=config.JWT_EXPIRES_HOURS)
    exp = datetime.fromtimestamp(payload["exp"], tz=timezone.utc)
    assert abs((exp - expected_exp).total_seconds()) < 60


def test_login_password_incorrecta_401(seeded_db):
    with TestClient(auth_app) as client:
        response = _login(client, _ADMIN_EMAIL, "incorrecta")
    assert response.status_code == 401


def test_login_email_desconocido_401(seeded_db):
    with TestClient(auth_app) as client:
        response = _login(client, "nadie@tienda.com", _ADMIN_PASSWORD)
    assert response.status_code == 401


def test_me_ok(seeded_db):
    with TestClient(auth_app) as client:
        token = _login(client, _EMPLEADO_EMAIL, _EMPLEADO_PASSWORD).json()["token"]
        response = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    assert response.json() == {
        "id": seeded_db["empleado"],
        "name": "Empleado",
        "email": _EMPLEADO_EMAIL,
        "role": "empleado",
    }


def test_me_sin_token_401(seeded_db):
    with TestClient(auth_app) as client:
        response = client.get("/auth/me")
    assert response.status_code == 401


def test_me_token_basura_401(seeded_db):
    with TestClient(auth_app) as client:
        response = client.get("/auth/me", headers={"Authorization": "Bearer no-es-un-jwt"})
    assert response.status_code == 401


def test_me_token_otro_secreto_401(seeded_db):
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(seeded_db["admin"]),
        "role": "admin",
        "name": "Admin",
        "exp": now + timedelta(hours=1),
    }
    token = jwt.encode(payload, "otro-secreto", algorithm="HS256")
    with TestClient(auth_app) as client:
        response = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 401


def test_me_token_expirado_401(seeded_db):
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(seeded_db["admin"]),
        "role": "admin",
        "name": "Admin",
        "exp": now - timedelta(hours=1),
    }
    token = jwt.encode(payload, config.JWT_SECRET, algorithm="HS256")
    with TestClient(auth_app) as client:
        response = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 401


def test_require_roles_admin_200():
    token = create_access_token(1, "admin", "Admin")
    with TestClient(_dummy_rbac_app()) as client:
        response = client.get("/admin-only", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    assert response.json()["role"] == "admin"


def test_require_roles_empleado_403():
    token = create_access_token(2, "empleado", "Empleado")
    with TestClient(_dummy_rbac_app()) as client:
        response = client.get("/admin-only", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 403


def test_require_roles_sin_token_401():
    with TestClient(_dummy_rbac_app()) as client:
        response = client.get("/admin-only")
    assert response.status_code == 401
