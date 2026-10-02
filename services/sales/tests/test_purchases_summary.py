"""Tests de GET /analytics/purchases-summary (F-005, paso 5).

Cubren el default (todas las órdenes), el rango opcional sobre `received_at`,
que sólo las recibidas suman spend, que `counts_by_status` es un snapshot de
todas las órdenes, el agrupado por mes y por proveedor (con nombre y orden desc),
el loop de páginas (>100 órdenes), from > to → 422, el RBAC y el 502 si
Inventario cae. Inventario se simula con `fake_inventory`.
"""

from fastapi.testclient import TestClient
from sales import rbac
from sales.main import app


def _auth(role: str = "admin", user_id: int = 1) -> dict:
    token = rbac.create_access_token(user_id=user_id, role=role, name="Ada")
    return {"Authorization": f"Bearer {token}"}


def _order(
    order_id: int,
    *,
    supplier_id: int,
    status: str,
    total: float,
    received_at: str | None = None,
    created_at: str = "2026-05-01T10:00:00",
) -> dict:
    return {
        "id": order_id,
        "supplier_id": supplier_id,
        "status": status,
        "expected_date": created_at,
        "created_at": created_at,
        "received_at": received_at,
        "total": total,
        "item_count": 1,
    }


def _sembrar(fake_inventory) -> None:
    # Recibidas: mayo (s1 100 + s2 50) y junio (s1 25).
    fake_inventory.purchase_orders = [
        _order(
            1,
            supplier_id=1,
            status="recibida",
            total=100.0,
            received_at="2026-05-10T10:00:00",
        ),
        _order(
            2,
            supplier_id=2,
            status="recibida",
            total=50.0,
            received_at="2026-05-20T10:00:00",
        ),
        _order(
            3,
            supplier_id=1,
            status="recibida",
            total=25.0,
            received_at="2026-06-01T09:00:00",
        ),
        # No recibidas: no suman spend pero sí cuentan en counts_by_status.
        _order(4, supplier_id=1, status="borrador", total=10.0),
        _order(5, supplier_id=2, status="enviada", total=20.0),
        _order(6, supplier_id=1, status="cancelada", total=30.0),
    ]
    fake_inventory.suppliers = [
        {"id": 1, "name": "Acme"},
        {"id": 2, "name": "Bodega"},
    ]


def _get(client: TestClient, url: str, role: str = "admin"):
    return client.get(url, headers=_auth(role=role))


def test_default_todas_las_ordenes(fake_inventory):
    _sembrar(fake_inventory)

    with TestClient(app) as client:
        response = _get(client, "/analytics/purchases-summary")

    assert response.status_code == 200
    totals = response.json()["totals"]
    assert totals["orders_received"] == 3
    assert totals["spend_received"] == 175.0


def test_rango_sobre_received_at_excluye_fuera(fake_inventory):
    _sembrar(fake_inventory)

    with TestClient(app) as client:
        response = _get(
            client,
            "/analytics/purchases-summary"
            "?date_from=2026-05-01&date_to=2026-05-31",
        )

    totals = response.json()["totals"]
    assert totals["orders_received"] == 2
    assert totals["spend_received"] == 150.0


def test_solo_recibidas_suman_spend(fake_inventory):
    _sembrar(fake_inventory)

    with TestClient(app) as client:
        response = _get(client, "/analytics/purchases-summary")

    body = response.json()
    # borrador(10)+enviada(20)+cancelada(30)=60 quedan fuera del spend.
    assert body["totals"]["spend_received"] == 175.0
    assert sum(item["spend"] for item in body["by_month"]) == 175.0


def test_counts_by_status_sobre_todas(fake_inventory):
    _sembrar(fake_inventory)

    with TestClient(app) as client:
        response = _get(
            client,
            "/analytics/purchases-summary"
            "?date_from=2026-05-01&date_to=2026-05-31",
        )

    assert response.json()["totals"]["counts_by_status"] == {
        "borrador": 1,
        "enviada": 1,
        "recibida": 3,
        "cancelada": 1,
    }


def test_by_month_orden_ascendente(fake_inventory):
    _sembrar(fake_inventory)

    with TestClient(app) as client:
        response = _get(client, "/analytics/purchases-summary")

    assert response.json()["by_month"] == [
        {"month": "2026-05", "orders": 2, "spend": 150.0},
        {"month": "2026-06", "orders": 1, "spend": 25.0},
    ]


def test_by_supplier_nombre_y_orden_desc(fake_inventory):
    _sembrar(fake_inventory)

    with TestClient(app) as client:
        response = _get(client, "/analytics/purchases-summary")

    assert response.json()["by_supplier"] == [
        {"supplier_id": 1, "supplier_name": "Acme", "orders": 2, "spend": 125.0},
        {"supplier_id": 2, "supplier_name": "Bodega", "orders": 1, "spend": 50.0},
    ]


def test_recorre_todas_las_paginas(fake_inventory):
    fake_inventory.purchase_orders = [
        _order(
            i,
            supplier_id=1,
            status="recibida",
            total=2.0,
            received_at="2026-05-10T10:00:00",
        )
        for i in range(1, 151)
    ]
    fake_inventory.suppliers = [{"id": 1, "name": "Acme"}]

    with TestClient(app) as client:
        response = _get(client, "/analytics/purchases-summary")

    body = response.json()
    assert body["totals"]["orders_received"] == 150
    assert body["totals"]["spend_received"] == 300.0
    pages = sum(
        1 for req in fake_inventory.requests if req.url.path == "/purchase-orders"
    )
    assert pages == 2


def test_from_mayor_que_to_422(fake_inventory):
    with TestClient(app) as client:
        response = _get(
            client,
            "/analytics/purchases-summary"
            "?date_from=2026-06-01&date_to=2026-05-01",
        )

    assert response.status_code == 422


def test_403_con_empleado(fake_inventory):
    with TestClient(app) as client:
        response = _get(client, "/analytics/purchases-summary", role="empleado")

    assert response.status_code == 403


def test_200_con_admin(fake_inventory):
    with TestClient(app) as client:
        response = _get(client, "/analytics/purchases-summary")

    assert response.status_code == 200


def test_502_si_inventory_falla(fake_inventory):
    fake_inventory.fail = True

    with TestClient(app) as client:
        response = _get(client, "/analytics/purchases-summary")

    assert response.status_code == 502
