"""Tests de GET /predictions (F-005, paso 6).

Cubren la predicción de una página: un producto con >=10 días de ventas usa
regresión, uno con pocas ventas cae a la media móvil y otro sin ventas devuelve
ceros/nullos con reorden = min_threshold − stock. Además: passthrough de `total`
y `page` del envelope de Inventario, `page_size` > 100 → 422, filtro por
categoría, RBAC admin-only y 502 si Inventario cae. Inventario se simula con
`fake_inventory`; el historial se inserta en la BD temporal de Ventas.
"""

from datetime import date, timedelta

from fastapi.testclient import TestClient
from sales import db, rbac
from sales.main import app
from sales.models import Sale, SaleItem

_PAGE_SIZE_DEFAULT = 50
_PAGE_SIZE_MAX = 100


def _product(
    product_id: int,
    *,
    name: str | None = None,
    category: str = "General",
    stock: int = 0,
    min_threshold: int = 0,
    state: str = "disponible",
    is_active: bool = True,
) -> dict:
    return {
        "id": product_id,
        "name": name or f"Producto {product_id}",
        "category": category,
        "stock": stock,
        "min_threshold": min_threshold,
        "state": state,
        "is_active": is_active,
    }


def _auth(role: str = "admin", user_id: int = 1) -> dict:
    token = rbac.create_access_token(user_id=user_id, role=role, name="Ada")
    return {"Authorization": f"Bearer {token}"}


def _insertar(sale_id: int, product_id: int, *, days_ago: int, quantity: int) -> None:
    """Inserta una venta (1 ítem) con `quantity` unidades hace `days_ago` días."""
    created_at = (
        date.today() - timedelta(days=days_ago)
    ).isoformat() + "T12:00:00"
    total = float(quantity)
    session = db.get_session_factory(db.get_engine())()
    try:
        session.add(
            Sale(id=sale_id, employee_id=1, total=total, created_at=created_at)
        )
        session.add(
            SaleItem(
                sale_id=sale_id,
                product_id=product_id,
                product_name=f"Producto {product_id}",
                category="General",
                quantity=quantity,
                unit_price=1.0,
                line_total=total,
            )
        )
        session.commit()
    finally:
        session.close()


def _sembrar_historial() -> None:
    """p1: 20 días de ventas crecientes; p2: 2 días; p3: sin ventas."""
    sale_id = 1
    for days_ago in range(20):
        _insertar(sale_id, 1, days_ago=days_ago, quantity=20 - days_ago)
        sale_id += 1
    for days_ago in (0, 1):
        _insertar(sale_id, 2, days_ago=days_ago, quantity=3)
        sale_id += 1


def _por_id(items: list[dict]) -> dict[int, dict]:
    return {item["product_id"]: item for item in items}


def _get(client: TestClient, url: str, role: str = "admin"):
    return client.get(url, headers=_auth(role=role))


def test_regresion_media_movil_y_sin_ventas(sales_db, fake_inventory):
    fake_inventory.products = [
        _product(1, category="Bebidas", stock=10, min_threshold=5, state="bajo"),
        _product(2, category="Snacks", stock=20, min_threshold=8),
        _product(3, category="Bebidas", stock=4, min_threshold=10, state="agotado"),
    ]
    _sembrar_historial()
    hoy = date.today()

    with TestClient(app) as client:
        response = _get(client, "/predictions")

    assert response.status_code == 200
    items = _por_id(response.json()["items"])

    # p1: >=10 días con ventas y pendiente positiva -> regresión.
    p1 = items[1]
    assert p1["method"] == "regresion"
    assert p1["daily_demand"] > 0
    # Coherente con la pendiente positiva: 'subiendo' con la banda muerta actual.
    assert p1["trend"] == "subiendo"
    assert p1["demand_30d"] == round(p1["daily_demand"] * 30)
    assert p1["suggested_reorder"] == max(
        0, round(p1["demand_30d"] + p1["min_threshold"] - p1["stock"])
    )
    assert p1["stockout_date"] == (
        hoy + timedelta(days=p1["stock"] / p1["daily_demand"])
    ).isoformat()

    # p2: sólo 2 días con ventas -> media móvil (3+3)/30 = 0.2.
    p2 = items[2]
    assert p2["method"] == "media_movil"
    assert p2["trend"] == "estable"
    assert p2["daily_demand"] == 0.2

    # p3: sin ventas -> ceros/nullos y reorden = min_threshold − stock.
    p3 = items[3]
    assert p3["method"] == "media_movil"
    assert p3["daily_demand"] == 0
    assert p3["demand_30d"] == 0
    assert p3["stockout_date"] is None
    assert p3["suggested_reorder"] == 10 - 4


def test_total_y_page_passthrough_del_envelope(sales_db, fake_inventory):
    fake_inventory.products = [_product(i) for i in range(1, 61)]

    with TestClient(app) as client:
        response = _get(client, "/predictions?page=2&page_size=50")

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 60
    assert body["page"] == 2
    assert body["page_size"] == 50
    assert len(body["items"]) == 10
    # Sólo se piden productos activos.
    assert fake_inventory.requests[0].url.params.get("is_active") == "true"


def test_defaults_page_y_page_size(sales_db, fake_inventory):
    fake_inventory.products = []

    with TestClient(app) as client:
        response = _get(client, "/predictions")

    body = response.json()
    assert body == {
        "items": [],
        "total": 0,
        "page": 1,
        "page_size": _PAGE_SIZE_DEFAULT,
    }


def test_page_size_mayor_que_100_es_422(sales_db, fake_inventory):
    with TestClient(app) as client:
        response = _get(client, f"/predictions?page_size={_PAGE_SIZE_MAX + 1}")

    assert response.status_code == 422


def test_category_filtra(sales_db, fake_inventory):
    fake_inventory.products = [
        _product(1, category="Bebidas"),
        _product(2, category="Snacks"),
        _product(3, category="Bebidas"),
    ]

    with TestClient(app) as client:
        response = _get(client, "/predictions?category=Bebidas")

    body = response.json()
    assert body["total"] == 2
    assert [item["product_id"] for item in body["items"]] == [1, 3]
    assert all(item["category"] == "Bebidas" for item in body["items"])


def test_403_con_empleado(sales_db, fake_inventory):
    fake_inventory.products = []

    with TestClient(app) as client:
        response = _get(client, "/predictions", role="empleado")

    assert response.status_code == 403


def test_200_con_admin(sales_db, fake_inventory):
    fake_inventory.products = []

    with TestClient(app) as client:
        response = _get(client, "/predictions")

    assert response.status_code == 200


def test_502_si_inventory_falla(sales_db, fake_inventory):
    fake_inventory.fail = True

    with TestClient(app) as client:
        response = _get(client, "/predictions")

    assert response.status_code == 502
