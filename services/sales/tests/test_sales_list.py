"""Tests de GET /sales y GET /sales/{id} (F-004, paso 8).

Cubre filtros (product_id, category, employee_id, rango de fechas), el borde de
date_to con fecha-sola (incluye el día completo), paginación (default 50, máx
100), ítems embebidos, orden por fecha desc, detalle 404 y autenticación.
"""

from fastapi.testclient import TestClient
from sales import db, rbac
from sales.main import app
from sales.models import Sale, SaleItem


def _auth(role: str = "empleado", user_id: int = 7) -> dict:
    token = rbac.create_access_token(user_id=user_id, role=role, name="Eve")
    return {"Authorization": f"Bearer {token}"}


def _item(
    product_id: int,
    *,
    name: str = "Producto",
    category: str = "General",
    quantity: int = 1,
    unit_price: float = 1.0,
) -> dict:
    return {
        "product_id": product_id,
        "product_name": name,
        "category": category,
        "quantity": quantity,
        "unit_price": unit_price,
        "line_total": quantity * unit_price,
    }


def _insertar(
    sale_id: int,
    *,
    employee_id: int,
    created_at: str,
    items: list[dict],
) -> None:
    session = db.get_session_factory(db.get_engine())()
    try:
        session.add(
            Sale(
                id=sale_id,
                employee_id=employee_id,
                total=sum(item["line_total"] for item in items),
                created_at=created_at,
            )
        )
        for item in items:
            session.add(SaleItem(sale_id=sale_id, **item))
        session.commit()
    finally:
        session.close()


def test_listar_default_paginacion_items_embebidos_orden_desc(sales_db):
    _insertar(
        1,
        employee_id=7,
        created_at="2026-05-01T10:00:00",
        items=[_item(1, name="Arroz", category="Alimentos", quantity=2, unit_price=1.5)],
    )
    _insertar(
        2,
        employee_id=8,
        created_at="2026-05-03T09:00:00",
        items=[_item(2, name="Leche", category="Lacteos", quantity=1, unit_price=2.0)],
    )

    with TestClient(app) as client:
        response = client.get("/sales", headers=_auth())

    assert response.status_code == 200
    body = response.json()
    assert set(body) == {"items", "total", "page", "page_size"}
    assert body["total"] == 2
    assert body["page"] == 1
    assert body["page_size"] == 50
    # Orden por fecha desc.
    assert [venta["id"] for venta in body["items"]] == [2, 1]
    venta = body["items"][1]
    assert venta["employee_id"] == 7
    assert venta["total"] == 3.0
    assert venta["created_at"] == "2026-05-01T10:00:00"
    assert venta["items"] == [
        {
            "id": 1,
            "product_id": 1,
            "product_name": "Arroz",
            "category": "Alimentos",
            "quantity": 2,
            "unit_price": 1.5,
            "line_total": 3.0,
        }
    ]


def test_filtro_product_id_solo_ventas_con_ese_item(sales_db):
    _insertar(
        1,
        employee_id=7,
        created_at="2026-05-01T10:00:00",
        items=[_item(1), _item(2)],
    )
    _insertar(
        2,
        employee_id=7,
        created_at="2026-05-02T10:00:00",
        items=[_item(3)],
    )

    with TestClient(app) as client:
        response = client.get("/sales", params={"product_id": 2}, headers=_auth())

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert [venta["id"] for venta in body["items"]] == [1]


def test_filtro_category_solo_ventas_con_ese_item(sales_db):
    _insertar(
        1,
        employee_id=7,
        created_at="2026-05-01T10:00:00",
        items=[_item(1, category="Alimentos"), _item(2, category="Lacteos")],
    )
    _insertar(
        2,
        employee_id=7,
        created_at="2026-05-02T10:00:00",
        items=[_item(3, category="Bebidas")],
    )

    with TestClient(app) as client:
        response = client.get("/sales", params={"category": "Lacteos"}, headers=_auth())

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert [venta["id"] for venta in body["items"]] == [1]


def test_filtro_employee_id(sales_db):
    _insertar(
        1, employee_id=7, created_at="2026-05-01T10:00:00", items=[_item(1)]
    )
    _insertar(
        2, employee_id=8, created_at="2026-05-02T10:00:00", items=[_item(2)]
    )

    with TestClient(app) as client:
        response = client.get("/sales", params={"employee_id": 8}, headers=_auth())

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert [venta["id"] for venta in body["items"]] == [2]


def test_filtro_rango_fechas_datetime(sales_db):
    _insertar(
        1, employee_id=7, created_at="2026-05-01T10:00:00", items=[_item(1)]
    )
    _insertar(
        2, employee_id=7, created_at="2026-05-02T15:00:00", items=[_item(2)]
    )
    _insertar(
        3, employee_id=7, created_at="2026-05-03T20:00:00", items=[_item(3)]
    )

    with TestClient(app) as client:
        response = client.get(
            "/sales",
            params={
                "date_from": "2026-05-02T00:00:00",
                "date_to": "2026-05-02T23:59:59.999999",
            },
            headers=_auth(),
        )

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert [venta["id"] for venta in body["items"]] == [2]


def test_date_to_solo_fecha_incluye_todo_el_dia(sales_db):
    _insertar(
        1, employee_id=7, created_at="2026-05-01T00:00:00", items=[_item(1)]
    )
    _insertar(
        2, employee_id=7, created_at="2026-05-01T23:59:59", items=[_item(2)]
    )
    _insertar(
        3, employee_id=7, created_at="2026-05-02T00:30:00", items=[_item(3)]
    )

    with TestClient(app) as client:
        response = client.get(
            "/sales", params={"date_to": "2026-05-01"}, headers=_auth()
        )

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 2
    assert [venta["id"] for venta in body["items"]] == [2, 1]


def test_page_size_mayor_100_devuelve_422(sales_db):
    with TestClient(app) as client:
        response = client.get(
            "/sales", params={"page_size": 101}, headers=_auth()
        )
    assert response.status_code == 422


def test_get_detalle_con_items(sales_db):
    _insertar(
        1,
        employee_id=7,
        created_at="2026-05-01T10:00:00",
        items=[_item(1, name="Arroz", category="Alimentos"), _item(2)],
    )

    with TestClient(app) as client:
        response = client.get("/sales/1", headers=_auth())

    assert response.status_code == 200
    body = response.json()
    assert body["id"] == 1
    assert body["employee_id"] == 7
    assert [item["product_id"] for item in body["items"]] == [1, 2]


def test_get_detalle_404_si_no_existe(sales_db):
    with TestClient(app) as client:
        response = client.get("/sales/999", headers=_auth())
    assert response.status_code == 404


def test_listar_401_sin_token(sales_db):
    with TestClient(app) as client:
        response = client.get("/sales")
    assert response.status_code == 401


def test_get_detalle_401_sin_token(sales_db):
    with TestClient(app) as client:
        response = client.get("/sales/1")
    assert response.status_code == 401


def test_listar_admin_y_empleado_autenticados(sales_db):
    _insertar(
        1, employee_id=7, created_at="2026-05-01T10:00:00", items=[_item(1)]
    )

    with TestClient(app) as client:
        assert client.get("/sales", headers=_auth(role="admin")).status_code == 200
        assert client.get("/sales", headers=_auth(role="empleado")).status_code == 200
