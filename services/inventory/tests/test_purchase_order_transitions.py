"""Tests de transiciones de órdenes de compra (F-004, paso 5).

Cubre /send (borrador→enviada), /cancel (enviada→cancelada sin tocar stock) y
/receive (enviada→recibida: suma stock por ítem y crea movimientos entrada
reason=compra con reference="po:{id}"). Usa la fixture seeded_db de conftest.py.
"""

import pytest
from fastapi.testclient import TestClient
from inventory import rbac
from inventory.main import app

_ADMIN_HEADERS = {
    "Authorization": f"Bearer {rbac.create_access_token(1, 'admin', 'Admin')}"
}
_EMPLOYEE_HEADERS = {
    "Authorization": f"Bearer {rbac.create_access_token(2, 'empleado', 'Empleado')}"
}


def _stock(client, product_id: int, headers: dict) -> int:
    response = client.get(f"/products/{product_id}", headers=headers)
    assert response.status_code == 200
    return response.json()["stock"]


def test_send_borrador_a_enviada(seeded_db):
    order_id = seeded_db["po_borrador"]
    with TestClient(app) as client:
        response = client.post(
            f"/purchase-orders/{order_id}/send", headers=_ADMIN_HEADERS
        )
        detalle = client.get(f"/purchase-orders/{order_id}", headers=_ADMIN_HEADERS)

    assert response.status_code == 200
    assert response.json()["status"] == "enviada"
    assert detalle.json()["status"] == "enviada"


def test_send_409_si_no_esta_en_borrador(seeded_db):
    with TestClient(app) as client:
        response = client.post(
            f"/purchase-orders/{seeded_db['po_enviada']}/send",
            headers=_ADMIN_HEADERS,
        )
    assert response.status_code == 409


def test_send_404_si_no_existe(seeded_db):
    with TestClient(app) as client:
        response = client.post("/purchase-orders/999999/send", headers=_ADMIN_HEADERS)
    assert response.status_code == 404


def test_cancel_enviada_sin_tocar_stock(seeded_db):
    order_id = seeded_db["po_enviada"]
    with TestClient(app) as client:
        antes = _stock(client, seeded_db["exceso"], _ADMIN_HEADERS)
        response = client.post(
            f"/purchase-orders/{order_id}/cancel", headers=_ADMIN_HEADERS
        )
        despues = _stock(client, seeded_db["exceso"], _ADMIN_HEADERS)

    assert response.status_code == 200
    assert response.json()["status"] == "cancelada"
    assert despues == antes


def test_cancel_409_si_no_esta_enviada(seeded_db):
    with TestClient(app) as client:
        response = client.post(
            f"/purchase-orders/{seeded_db['po_borrador']}/cancel",
            headers=_ADMIN_HEADERS,
        )
    assert response.status_code == 409


def test_cancel_404_si_no_existe(seeded_db):
    with TestClient(app) as client:
        response = client.post(
            "/purchase-orders/999999/cancel", headers=_ADMIN_HEADERS
        )
    assert response.status_code == 404


def test_receive_suma_stock_y_crea_movimiento(seeded_db):
    order_id = seeded_db["po_enviada"]
    product_id = seeded_db["exceso"]
    with TestClient(app) as client:
        antes = _stock(client, product_id, _ADMIN_HEADERS)
        response = client.post(
            f"/purchase-orders/{order_id}/receive", headers=_ADMIN_HEADERS
        )
        despues = _stock(client, product_id, _ADMIN_HEADERS)
        movimientos = client.get(
            "/movements",
            params={"product_id": product_id, "reason": "compra"},
            headers=_ADMIN_HEADERS,
        )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "recibida"
    assert body["received_at"] is not None
    assert despues == antes + 4

    items = movimientos.json()["items"]
    assert movimientos.status_code == 200
    creado = [m for m in items if m["reference"] == f"po:{order_id}"]
    assert len(creado) == 1
    assert creado[0]["movement_type"] == "entrada"
    assert creado[0]["reason"] == "compra"
    assert creado[0]["quantity"] == 4
    assert creado[0]["created_at"] == body["received_at"]


def test_receive_crea_un_movimiento_por_item(seeded_db):
    order_id = seeded_db["po_borrador"]
    with TestClient(app) as client:
        client.post(f"/purchase-orders/{order_id}/send", headers=_ADMIN_HEADERS)
        response = client.post(
            f"/purchase-orders/{order_id}/receive", headers=_ADMIN_HEADERS
        )
        movimientos = client.get(
            "/movements",
            params={"reason": "compra"},
            headers=_ADMIN_HEADERS,
        )

    assert response.status_code == 200
    received_at = response.json()["received_at"]
    creados = [
        m
        for m in movimientos.json()["items"]
        if m["reference"] == f"po:{order_id}" and m["created_at"] == received_at
    ]
    assert len(creados) == 2
    assert {m["product_id"] for m in creados} == {
        seeded_db["disponible"],
        seeded_db["bajo"],
    }


def test_receive_409_si_no_esta_enviada(seeded_db):
    with TestClient(app) as client:
        response = client.post(
            f"/purchase-orders/{seeded_db['po_borrador']}/receive",
            headers=_ADMIN_HEADERS,
        )
    assert response.status_code == 409


def test_receive_404_si_no_existe(seeded_db):
    with TestClient(app) as client:
        response = client.post(
            "/purchase-orders/999999/receive", headers=_ADMIN_HEADERS
        )
    assert response.status_code == 404


def test_receive_empleado_autorizado(seeded_db):
    order_id = seeded_db["po_enviada"]
    with TestClient(app) as client:
        response = client.post(
            f"/purchase-orders/{order_id}/receive", headers=_EMPLOYEE_HEADERS
        )
    assert response.status_code == 200
    assert response.json()["status"] == "recibida"


def test_send_y_cancel_empleado_403(seeded_db):
    with TestClient(app) as client:
        send = client.post(
            f"/purchase-orders/{seeded_db['po_borrador']}/send",
            headers=_EMPLOYEE_HEADERS,
        )
        cancel = client.post(
            f"/purchase-orders/{seeded_db['po_enviada']}/cancel",
            headers=_EMPLOYEE_HEADERS,
        )
    assert send.status_code == 403
    assert cancel.status_code == 403


@pytest.mark.parametrize("action", ["send", "cancel", "receive"])
def test_acciones_sin_token_401(seeded_db, action):
    with TestClient(app) as client:
        response = client.post(
            f"/purchase-orders/{seeded_db['po_borrador']}/{action}"
        )
    assert response.status_code == 401
