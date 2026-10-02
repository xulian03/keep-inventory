"""Tests de GET /analytics/kpis (F-005, paso 3).

Cubren el período por defecto (30 días), el rango explícito, el delta vs el
período anterior (null si éste no tuvo ventas), la agregación del inventario
recorriendo todas las páginas y el RBAC admin-only. Inventario se simula con la
fixture `fake_inventory`; las ventas se insertan en la BD temporal.
"""

from datetime import date, timedelta

from fastapi.testclient import TestClient
from sales import db, rbac
from sales.main import app
from sales.models import Sale, SaleItem

_DIAS_DEFAULT = 29


def _product(
    product_id: int,
    *,
    stock: int = 0,
    sale_price: float = 1.0,
    state: str = "disponible",
) -> dict:
    return {
        "id": product_id,
        "stock": stock,
        "sale_price": sale_price,
        "state": state,
        "is_active": True,
    }


def _auth(role: str = "admin", user_id: int = 1) -> dict:
    token = rbac.create_access_token(user_id=user_id, role=role, name="Ada")
    return {"Authorization": f"Bearer {token}"}


def _insertar(
    sale_id: int,
    *,
    created_at: str,
    quantity: int = 1,
    unit_price: float = 1.0,
    category: str = "General",
) -> None:
    session = db.get_session_factory(db.get_engine())()
    try:
        total = quantity * unit_price
        session.add(
            Sale(id=sale_id, employee_id=1, total=total, created_at=created_at)
        )
        session.add(
            SaleItem(
                sale_id=sale_id,
                product_id=1,
                product_name="Producto",
                category=category,
                quantity=quantity,
                unit_price=unit_price,
                line_total=total,
            )
        )
        session.commit()
    finally:
        session.close()


def _get(client: TestClient, url: str, role: str = "admin"):
    return client.get(url, headers=_auth(role=role))


def test_kpis_default_30_dias(sales_db, fake_inventory):
    fake_inventory.products = [_product(1, stock=2, sale_price=1.5, state="bajo")]
    hoy = date.today()

    with TestClient(app) as client:
        response = _get(client, "/analytics/kpis")

    assert response.status_code == 200
    body = response.json()
    assert body["period"] == {
        "from": (hoy - timedelta(days=_DIAS_DEFAULT)).isoformat(),
        "to": hoy.isoformat(),
    }
    assert body["sales"]["total"] == 0.0
    assert body["sales"]["transactions"] == 0
    assert body["inventory"] == {
        "value": 3.0,
        "products_total": 1,
        "counts": {"agotado": 0, "bajo": 1, "disponible": 0, "exceso": 0},
    }


def test_kpis_rango_explicito(sales_db, fake_inventory):
    fake_inventory.products = []
    _insertar(1, created_at="2026-05-12T10:00:00", quantity=3, unit_price=2.0)
    _insertar(2, created_at="2026-06-01T10:00:00", quantity=5, unit_price=2.0)

    with TestClient(app) as client:
        response = _get(
            client, "/analytics/kpis?date_from=2026-05-11&date_to=2026-05-20"
        )

    body = response.json()
    assert body["period"] == {"from": "2026-05-11", "to": "2026-05-20"}
    assert body["sales"]["total"] == 6.0
    assert body["sales"]["transactions"] == 1
    assert body["sales"]["units"] == 3
    assert body["inventory"]["products_total"] == 0


def test_kpis_delta_null_si_anterior_vacio(sales_db, fake_inventory):
    fake_inventory.products = []
    _insertar(1, created_at="2026-05-12T10:00:00", quantity=2, unit_price=3.0)

    with TestClient(app) as client:
        response = _get(
            client, "/analytics/kpis?date_from=2026-05-11&date_to=2026-05-20"
        )

    assert response.json()["sales"]["delta_pct"] == {
        "total": None,
        "transactions": None,
        "avg_ticket": None,
        "units": None,
    }


def test_kpis_delta_numerico_con_ambos_periodos(sales_db, fake_inventory):
    fake_inventory.products = []
    # Período anterior 2026-05-01..2026-05-10: total 3.0, 2 uds, 1 venta.
    _insertar(1, created_at="2026-05-05T10:00:00", quantity=2, unit_price=1.5)
    # Período actual 2026-05-11..2026-05-20: total 9.0, 4 uds, 2 ventas.
    _insertar(2, created_at="2026-05-12T10:00:00", quantity=3, unit_price=2.0)
    _insertar(3, created_at="2026-05-15T10:00:00", quantity=1, unit_price=3.0)

    with TestClient(app) as client:
        response = _get(
            client, "/analytics/kpis?date_from=2026-05-11&date_to=2026-05-20"
        )

    sales = response.json()["sales"]
    assert sales["total"] == 9.0
    assert sales["transactions"] == 2
    assert sales["avg_ticket"] == 4.5
    assert sales["units"] == 4
    assert sales["delta_pct"] == {
        "total": 200.0,
        "transactions": 100.0,
        "avg_ticket": 50.0,
        "units": 100.0,
    }


def test_kpis_inventario_value_y_counts(sales_db, fake_inventory):
    fake_inventory.products = [
        _product(1, stock=4, sale_price=2.5, state="agotado"),
        _product(2, stock=3, sale_price=1.0, state="bajo"),
        _product(3, stock=10, sale_price=2.0, state="disponible"),
        _product(4, stock=5, sale_price=1.0, state="exceso"),
    ]

    with TestClient(app) as client:
        response = _get(client, "/analytics/kpis")

    inventory = response.json()["inventory"]
    assert inventory["value"] == 38.0
    assert inventory["products_total"] == 4
    assert inventory["counts"] == {
        "agotado": 1,
        "bajo": 1,
        "disponible": 1,
        "exceso": 1,
    }


def test_kpis_inventario_recorre_todas_las_paginas(sales_db, fake_inventory):
    fake_inventory.products = [
        _product(i, stock=2, sale_price=1.0, state="disponible")
        for i in range(1, 151)
    ]

    with TestClient(app) as client:
        response = _get(client, "/analytics/kpis")

    inventory = response.json()["inventory"]
    assert inventory["value"] == 300.0
    assert inventory["products_total"] == 150
    assert inventory["counts"]["disponible"] == 150
    assert len(fake_inventory.requests) == 2


def test_kpis_403_con_token_empleado(sales_db, fake_inventory):
    fake_inventory.products = []

    with TestClient(app) as client:
        response = _get(client, "/analytics/kpis", role="empleado")

    assert response.status_code == 403


def test_kpis_200_con_admin(sales_db, fake_inventory):
    fake_inventory.products = []

    with TestClient(app) as client:
        response = _get(client, "/analytics/kpis")

    assert response.status_code == 200
