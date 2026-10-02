"""Tests de /sales-trend, /sales-by-category y /top-products (F-005, paso 4).

Cubren group_by day/week/month con datos que cruzan un lunes ISO y un cambio de
mes, el filtro por categoría, el rango parcial, from > to → 422, el límite del
top, points vacío sin ventas y el RBAC admin-only. Las ventas se insertan en la
BD temporal; estos endpoints no llaman a Inventario.
"""

from datetime import date, timedelta

from fastapi.testclient import TestClient
from sales import db, rbac
from sales.main import app
from sales.models import Sale, SaleItem

_DIAS_DEFAULT = 29
_TRES_ENDPOINTS = (
    "/analytics/sales-trend",
    "/analytics/sales-by-category",
    "/analytics/top-products",
)


def _auth(role: str = "admin", user_id: int = 1) -> dict:
    token = rbac.create_access_token(user_id=user_id, role=role, name="Ada")
    return {"Authorization": f"Bearer {token}"}


def _insertar(
    sale_id: int,
    *,
    created_at: str,
    product_id: int,
    product_name: str,
    category: str,
    quantity: int,
    unit_price: float,
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
                product_id=product_id,
                product_name=product_name,
                category=category,
                quantity=quantity,
                unit_price=unit_price,
                line_total=total,
            )
        )
        session.commit()
    finally:
        session.close()


def _sembrar() -> None:
    # Jue 2026-04-30 (semana ISO del lunes 04-27).
    _insertar(
        1,
        created_at="2026-04-30T10:00:00",
        product_id=1,
        product_name="Arroz",
        category="Alimentos",
        quantity=2,
        unit_price=1.0,
    )
    # Sáb 2026-05-02 (misma semana ISO que el 04-30).
    _insertar(
        2,
        created_at="2026-05-02T10:00:00",
        product_id=2,
        product_name="Jugo",
        category="Bebidas",
        quantity=3,
        unit_price=2.0,
    )
    # Lun 2026-05-04 y Mar 2026-05-05 (semana siguiente).
    _insertar(
        3,
        created_at="2026-05-04T10:00:00",
        product_id=1,
        product_name="Arroz",
        category="Alimentos",
        quantity=1,
        unit_price=5.0,
    )
    _insertar(
        4,
        created_at="2026-05-05T10:00:00",
        product_id=3,
        product_name="Leche",
        category="Lacteos",
        quantity=4,
        unit_price=1.0,
    )
    # Dom 2026-05-31 (semana ISO del lunes 05-25).
    _insertar(
        5,
        created_at="2026-05-31T10:00:00",
        product_id=2,
        product_name="Jugo",
        category="Bebidas",
        quantity=2,
        unit_price=2.0,
    )
    # Lun 2026-06-01 (cambio de mes y de semana ISO).
    _insertar(
        6,
        created_at="2026-06-01T10:00:00",
        product_id=1,
        product_name="Arroz",
        category="Alimentos",
        quantity=1,
        unit_price=3.0,
    )


def _get(client: TestClient, url: str, role: str = "admin"):
    return client.get(url, headers=_auth(role=role))


def test_trend_group_by_day_por_defecto(sales_db):
    _sembrar()

    with TestClient(app) as client:
        response = _get(
            client, "/analytics/sales-trend?date_from=2026-04-01&date_to=2026-06-30"
        )

    assert response.status_code == 200
    body = response.json()
    assert body["group_by"] == "day"
    assert body["from"] == "2026-04-01"
    assert body["to"] == "2026-06-30"
    assert body["points"] == [
        {"bucket": "2026-04-30", "total": 2.0, "units": 2, "transactions": 1},
        {"bucket": "2026-05-02", "total": 6.0, "units": 3, "transactions": 1},
        {"bucket": "2026-05-04", "total": 5.0, "units": 1, "transactions": 1},
        {"bucket": "2026-05-05", "total": 4.0, "units": 4, "transactions": 1},
        {"bucket": "2026-05-31", "total": 4.0, "units": 2, "transactions": 1},
        {"bucket": "2026-06-01", "total": 3.0, "units": 1, "transactions": 1},
    ]


def test_trend_group_by_week_pliega_al_lunes_iso(sales_db):
    _sembrar()

    with TestClient(app) as client:
        response = _get(
            client,
            "/analytics/sales-trend?group_by=week"
            "&date_from=2026-04-01&date_to=2026-06-30",
        )

    assert response.json()["points"] == [
        {"bucket": "2026-04-27", "total": 8.0, "units": 5, "transactions": 2},
        {"bucket": "2026-05-04", "total": 9.0, "units": 5, "transactions": 2},
        {"bucket": "2026-05-25", "total": 4.0, "units": 2, "transactions": 1},
        {"bucket": "2026-06-01", "total": 3.0, "units": 1, "transactions": 1},
    ]


def test_trend_group_by_month_pliega_por_mes(sales_db):
    _sembrar()

    with TestClient(app) as client:
        response = _get(
            client,
            "/analytics/sales-trend?group_by=month"
            "&date_from=2026-04-01&date_to=2026-06-30",
        )

    assert response.json()["points"] == [
        {"bucket": "2026-04", "total": 2.0, "units": 2, "transactions": 1},
        {"bucket": "2026-05", "total": 19.0, "units": 10, "transactions": 4},
        {"bucket": "2026-06", "total": 3.0, "units": 1, "transactions": 1},
    ]


def test_trend_filtra_por_categoria(sales_db):
    _sembrar()

    with TestClient(app) as client:
        response = _get(
            client,
            "/analytics/sales-trend?group_by=week&category=Bebidas"
            "&date_from=2026-04-01&date_to=2026-06-30",
        )

    assert response.json()["points"] == [
        {"bucket": "2026-04-27", "total": 6.0, "units": 3, "transactions": 1},
        {"bucket": "2026-05-25", "total": 4.0, "units": 2, "transactions": 1},
    ]


def test_trend_rango_parcial(sales_db):
    _sembrar()

    with TestClient(app) as client:
        response = _get(
            client,
            "/analytics/sales-trend?date_from=2026-05-04&date_to=2026-05-05",
        )

    body = response.json()
    assert body["from"] == "2026-05-04"
    assert body["to"] == "2026-05-05"
    assert body["points"] == [
        {"bucket": "2026-05-04", "total": 5.0, "units": 1, "transactions": 1},
        {"bucket": "2026-05-05", "total": 4.0, "units": 4, "transactions": 1},
    ]


def test_trend_sin_ventas_devuelve_points_vacio(sales_db):
    _sembrar()

    with TestClient(app) as client:
        response = _get(
            client, "/analytics/sales-trend?date_from=2020-01-01&date_to=2020-01-31"
        )

    assert response.status_code == 200
    assert response.json()["points"] == []


def test_trend_rango_por_defecto_ultimos_30_dias(sales_db):
    hoy = date.today()

    with TestClient(app) as client:
        response = _get(client, "/analytics/sales-trend")

    body = response.json()
    assert body["from"] == (hoy - timedelta(days=_DIAS_DEFAULT)).isoformat()
    assert body["to"] == hoy.isoformat()
    assert body["points"] == []


def test_trend_from_mayor_que_to_422(sales_db):
    with TestClient(app) as client:
        response = _get(
            client, "/analytics/sales-trend?date_from=2026-06-01&date_to=2026-05-01"
        )

    assert response.status_code == 422


def test_trend_group_by_invalido_422(sales_db):
    with TestClient(app) as client:
        response = _get(client, "/analytics/sales-trend?group_by=year")

    assert response.status_code == 422


def test_sales_by_category_desc_por_total(sales_db):
    _sembrar()

    with TestClient(app) as client:
        response = _get(
            client,
            "/analytics/sales-by-category"
            "?date_from=2026-04-01&date_to=2026-06-30",
        )

    assert response.status_code == 200
    assert response.json()["items"] == [
        {"category": "Alimentos", "total": 10.0, "units": 4},
        {"category": "Bebidas", "total": 10.0, "units": 5},
        {"category": "Lacteos", "total": 4.0, "units": 4},
    ]


def test_sales_by_category_rango_vacio(sales_db):
    _sembrar()

    with TestClient(app) as client:
        response = _get(
            client,
            "/analytics/sales-by-category?date_from=2020-01-01&date_to=2020-01-31",
        )

    assert response.json()["items"] == []


def test_sales_by_category_from_mayor_que_to_422(sales_db):
    with TestClient(app) as client:
        response = _get(
            client,
            "/analytics/sales-by-category"
            "?date_from=2026-06-01&date_to=2026-05-01",
        )

    assert response.status_code == 422


def test_top_products_orden_y_default_limit(sales_db):
    _sembrar()

    with TestClient(app) as client:
        response = _get(
            client,
            "/analytics/top-products?date_from=2026-04-01&date_to=2026-06-30",
        )

    assert response.status_code == 200
    assert response.json()["items"] == [
        {
            "product_id": 1,
            "product_name": "Arroz",
            "category": "Alimentos",
            "units": 4,
            "total": 10.0,
        },
        {
            "product_id": 2,
            "product_name": "Jugo",
            "category": "Bebidas",
            "units": 5,
            "total": 10.0,
        },
        {
            "product_id": 3,
            "product_name": "Leche",
            "category": "Lacteos",
            "units": 4,
            "total": 4.0,
        },
    ]


def test_top_products_recorta_a_limit(sales_db):
    _sembrar()

    with TestClient(app) as client:
        response = _get(
            client,
            "/analytics/top-products?limit=2"
            "&date_from=2026-04-01&date_to=2026-06-30",
        )

    items = response.json()["items"]
    assert [item["product_id"] for item in items] == [1, 2]


def test_top_products_filtra_por_categoria(sales_db):
    _sembrar()

    with TestClient(app) as client:
        response = _get(
            client,
            "/analytics/top-products?category=Bebidas"
            "&date_from=2026-04-01&date_to=2026-06-30",
        )

    assert response.json()["items"] == [
        {
            "product_id": 2,
            "product_name": "Jugo",
            "category": "Bebidas",
            "units": 5,
            "total": 10.0,
        }
    ]


def test_top_products_limit_maximo(sales_db):
    _sembrar()

    with TestClient(app) as client:
        ok = _get(client, "/analytics/top-products?limit=50")
        too_much = _get(client, "/analytics/top-products?limit=51")

    assert ok.status_code == 200
    assert too_much.status_code == 422


def test_top_products_from_mayor_que_to_422(sales_db):
    with TestClient(app) as client:
        response = _get(
            client, "/analytics/top-products?date_from=2026-06-01&date_to=2026-05-01"
        )

    assert response.status_code == 422


def test_endpoints_403_con_empleado(sales_db):
    with TestClient(app) as client:
        for endpoint in _TRES_ENDPOINTS:
            response = _get(client, endpoint, role="empleado")
            assert response.status_code == 403, endpoint


def test_endpoints_200_con_admin(sales_db):
    _sembrar()

    with TestClient(app) as client:
        for endpoint in _TRES_ENDPOINTS:
            response = _get(client, endpoint, role="admin")
            assert response.status_code == 200, endpoint
