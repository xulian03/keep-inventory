"""Tests del descuento interno por venta (F-004, paso 6).

Cubre POST /internal/movements/salida: descuento por lote atómico, un
movimiento (salida, reason=venta, reference) por ítem, 409 sin descontar nada
si falta stock o un producto no existe, 401 sin token y 422 con lote inválido.
Usa la fixture seeded_db de conftest.py.
"""

import pytest
from fastapi.testclient import TestClient
from inventory import rbac
from inventory.main import app

_HEADERS = {
    "Authorization": f"Bearer {rbac.create_access_token(1, 'empleado', 'Empleado')}"
}


def _stock(client, product_id: int) -> int:
    response = client.get(f"/products/{product_id}", headers=_HEADERS)
    assert response.status_code == 200
    return response.json()["stock"]


def test_salida_200_descuenta_y_crea_movimiento_por_item(seeded_db):
    payload = {
        "reference": "venta:test-1",
        "items": [
            {"product_id": seeded_db["disponible"], "quantity": 10},
            {"product_id": seeded_db["bajo"], "quantity": 2},
        ],
    }
    with TestClient(app) as client:
        response = client.post(
            "/internal/movements/salida", json=payload, headers=_HEADERS
        )
        disponible = _stock(client, seeded_db["disponible"])
        bajo = _stock(client, seeded_db["bajo"])
        movimientos = client.get(
            "/movements", params={"reason": "venta"}, headers=_HEADERS
        )

    assert response.status_code == 200
    assert response.json() == {
        "items": [
            {"product_id": seeded_db["disponible"], "stock": 40},
            {"product_id": seeded_db["bajo"], "stock": 3},
        ]
    }
    assert disponible == 40
    assert bajo == 3

    creados = [
        m for m in movimientos.json()["items"] if m["reference"] == "venta:test-1"
    ]
    assert len(creados) == 2
    assert {m["product_id"] for m in creados} == {
        seeded_db["disponible"],
        seeded_db["bajo"],
    }
    assert all(m["movement_type"] == "salida" and m["reason"] == "venta" for m in creados)
    assert {(m["product_id"], m["quantity"]) for m in creados} == {
        (seeded_db["disponible"], 10),
        (seeded_db["bajo"], 2),
    }


def test_salida_409_sin_stock_no_descuenta_nada(seeded_db):
    payload = {
        "reference": "venta:test-2",
        "items": [
            {"product_id": seeded_db["disponible"], "quantity": 10},
            {"product_id": seeded_db["bajo"], "quantity": 999},
        ],
    }
    with TestClient(app) as client:
        response = client.post(
            "/internal/movements/salida", json=payload, headers=_HEADERS
        )
        disponible = _stock(client, seeded_db["disponible"])
        bajo = _stock(client, seeded_db["bajo"])
        movimientos = client.get(
            "/movements",
            params={"reason": "venta", "product_id": seeded_db["disponible"]},
            headers=_HEADERS,
        )

    assert response.status_code == 409
    assert disponible == 50
    assert bajo == 5
    assert not [
        m for m in movimientos.json()["items"] if m["reference"] == "venta:test-2"
    ]


def test_salida_409_producto_inexistente_no_descuenta_nada(seeded_db):
    payload = {
        "reference": "venta:test-3",
        "items": [
            {"product_id": seeded_db["disponible"], "quantity": 1},
            {"product_id": 999999, "quantity": 1},
        ],
    }
    with TestClient(app) as client:
        response = client.post(
            "/internal/movements/salida", json=payload, headers=_HEADERS
        )
        disponible = _stock(client, seeded_db["disponible"])

    assert response.status_code == 409
    assert disponible == 50


def test_salida_401_sin_token(seeded_db):
    payload = {
        "reference": "venta:test-4",
        "items": [{"product_id": seeded_db["disponible"], "quantity": 1}],
    }
    with TestClient(app) as client:
        response = client.post("/internal/movements/salida", json=payload)
    assert response.status_code == 401


@pytest.mark.parametrize("quantity", [0, -1])
def test_salida_422_quantity_invalida(seeded_db, quantity):
    payload = {
        "reference": "venta:test-5",
        "items": [{"product_id": seeded_db["disponible"], "quantity": quantity}],
    }
    with TestClient(app) as client:
        response = client.post(
            "/internal/movements/salida", json=payload, headers=_HEADERS
        )
    assert response.status_code == 422


def test_salida_422_items_duplicados(seeded_db):
    payload = {
        "reference": "venta:test-6",
        "items": [
            {"product_id": seeded_db["disponible"], "quantity": 1},
            {"product_id": seeded_db["disponible"], "quantity": 1},
        ],
    }
    with TestClient(app) as client:
        response = client.post(
            "/internal/movements/salida", json=payload, headers=_HEADERS
        )
    assert response.status_code == 422


def test_salida_422_items_vacio(seeded_db):
    payload = {"reference": "venta:test-7", "items": []}
    with TestClient(app) as client:
        response = client.post(
            "/internal/movements/salida", json=payload, headers=_HEADERS
        )
    assert response.status_code == 422
