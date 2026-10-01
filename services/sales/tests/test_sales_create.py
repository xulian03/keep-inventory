"""Tests de POST /sales (F-004, paso 7).

Cubre el flujo completo: catálogo (404/422), descuento atómico vía REST interno
(409 propagado), guardado local denormalizado (201) y compensación con entradas
reason=ajuste si falla el guardado tras descontar (502). Inventario se simula
con httpx.MockTransport, sin levantar el servicio.
"""

import json

import httpx
from fastapi.testclient import TestClient
from sales import db, rbac
from sales.inventory_client import InventoryClient, get_inventory_client
from sales.main import app
from sales.models import Sale, SaleItem

_PRODUCTS_PATH = "/products"
_SALIDA_PATH = "/internal/movements/salida"
_MOVEMENTS_PATH = "/movements"


def _product(
    product_id: int,
    *,
    name: str = "Producto",
    category: str = "General",
    sale_price: float = 1.0,
    stock: int = 10,
    is_active: bool = True,
) -> dict:
    return {
        "id": product_id,
        "name": name,
        "category": category,
        "sale_price": sale_price,
        "stock": stock,
        "is_active": is_active,
    }


class FakeInventory:
    """Handler de httpx.MockTransport que simula el servicio Inventario."""

    def __init__(self) -> None:
        self.products: dict[int, dict] = {}
        self.salida_status = 200
        self.products_caido = False
        self.salida_caido = False
        self.requests: list[httpx.Request] = []

    def handler(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        path = request.url.path
        if path == _PRODUCTS_PATH:
            if self.products_caido:
                raise httpx.ConnectError("sin conexión", request=request)
            ids = request.url.params.get("ids", "")
            wanted = {int(part) for part in ids.split(",") if part}
            items = [p for pid, p in self.products.items() if pid in wanted]
            return httpx.Response(200, json={"items": items})
        if path == _SALIDA_PATH:
            if self.salida_caido:
                raise httpx.ConnectError("sin conexión", request=request)
            if self.salida_status != 200:
                return httpx.Response(
                    self.salida_status, json={"detail": "conflicto"}
                )
            body = json.loads(request.content)
            stock = [
                {
                    "product_id": item["product_id"],
                    "stock": self.products[item["product_id"]]["stock"]
                    - item["quantity"],
                }
                for item in body["items"]
            ]
            return httpx.Response(200, json={"items": stock})
        if path == _MOVEMENTS_PATH:
            return httpx.Response(201, json={"movement": {}, "stock": 0})
        return httpx.Response(404, json={"detail": "no encontrado"})


def _usar_inventario(fake: FakeInventory) -> None:
    client = InventoryClient(
        base_url="http://inventario.test",
        transport=httpx.MockTransport(fake.handler),
    )
    app.dependency_overrides[get_inventory_client] = lambda: client


def _auth(role: str = "empleado", user_id: int = 7) -> dict:
    token = rbac.create_access_token(user_id=user_id, role=role, name="Eve")
    return {"Authorization": f"Bearer {token}"}


def _persistido() -> tuple[list[Sale], list[SaleItem]]:
    session = db.get_session_factory(db.get_engine())()
    try:
        return session.query(Sale).all(), session.query(SaleItem).all()
    finally:
        session.close()


def _payload(*items: tuple[int, int]) -> dict:
    return {"items": [{"product_id": pid, "quantity": qty} for pid, qty in items]}


def test_crear_venta_201_dos_items(sales_db):
    fake = FakeInventory()
    fake.products = {
        1: _product(1, name="Arroz", category="Alimentos", sale_price=1.5, stock=50),
        2: _product(2, name="Leche", category="Lacteos", sale_price=2.0, stock=10),
    }
    _usar_inventario(fake)

    with TestClient(app) as client:
        response = client.post("/sales", json=_payload((1, 2), (2, 3)), headers=_auth())

    assert response.status_code == 201
    body = response.json()
    assert body["venta"]["employee_id"] == 7
    assert body["venta"]["total"] == 9.0
    assert body["stock"] == [
        {"product_id": 1, "stock": 48},
        {"product_id": 2, "stock": 7},
    ]
    items = {item["product_id"]: item for item in body["venta"]["items"]}
    assert items[1]["product_name"] == "Arroz"
    assert items[1]["category"] == "Alimentos"
    assert items[1]["unit_price"] == 1.5
    assert items[1]["line_total"] == 3.0
    assert items[2]["line_total"] == 6.0

    ventas, lineas = _persistido()
    assert len(ventas) == 1 and ventas[0].total == 9.0
    assert len(lineas) == 2
    assert {linea.product_id for linea in lineas} == {1, 2}

    salida = next(r for r in fake.requests if r.url.path == _SALIDA_PATH)
    salida_body = json.loads(salida.content)
    assert salida_body["reference"].startswith("venta:")
    assert salida_body["items"] == [
        {"product_id": 1, "quantity": 2},
        {"product_id": 2, "quantity": 3},
    ]


def test_crear_venta_404_producto_inexistente(sales_db):
    fake = FakeInventory()
    fake.products = {1: _product(1, stock=10)}
    _usar_inventario(fake)

    with TestClient(app) as client:
        response = client.post("/sales", json=_payload((999, 1)), headers=_auth())

    assert response.status_code == 404
    assert not [r for r in fake.requests if r.url.path == _SALIDA_PATH]
    ventas, lineas = _persistido()
    assert ventas == [] and lineas == []


def test_crear_venta_422_producto_inactivo(sales_db):
    fake = FakeInventory()
    fake.products = {1: _product(1, stock=10, is_active=False)}
    _usar_inventario(fake)

    with TestClient(app) as client:
        response = client.post("/sales", json=_payload((1, 1)), headers=_auth())

    assert response.status_code == 422
    assert not [r for r in fake.requests if r.url.path == _SALIDA_PATH]
    ventas, _ = _persistido()
    assert ventas == []


def test_crear_venta_422_stock_insuficiente(sales_db):
    fake = FakeInventory()
    fake.products = {1: _product(1, stock=1)}
    _usar_inventario(fake)

    with TestClient(app) as client:
        response = client.post("/sales", json=_payload((1, 5)), headers=_auth())

    assert response.status_code == 422
    assert not [r for r in fake.requests if r.url.path == _SALIDA_PATH]
    ventas, _ = _persistido()
    assert ventas == []


def test_crear_venta_409_propagado_sin_registro(sales_db):
    fake = FakeInventory()
    fake.products = {1: _product(1, stock=10)}
    fake.salida_status = 409
    _usar_inventario(fake)

    with TestClient(app) as client:
        response = client.post("/sales", json=_payload((1, 1)), headers=_auth())

    assert response.status_code == 409
    assert not [r for r in fake.requests if r.url.path == _MOVEMENTS_PATH]
    ventas, _ = _persistido()
    assert ventas == []


def test_crear_venta_502_inventario_caido_sin_registro(sales_db):
    fake = FakeInventory()
    fake.products = {1: _product(1, stock=10)}
    fake.products_caido = True
    _usar_inventario(fake)

    with TestClient(app) as client:
        response = client.post("/sales", json=_payload((1, 1)), headers=_auth())

    assert response.status_code == 502
    ventas, _ = _persistido()
    assert ventas == []


def test_crear_venta_502_compensa_si_falla_guardado(sales_db, monkeypatch):
    fake = FakeInventory()
    fake.products = {1: _product(1, sale_price=2.0, stock=10)}
    _usar_inventario(fake)

    def _fallo(*args, **kwargs):
        raise RuntimeError("fallo de escritura local")

    monkeypatch.setattr("sales.routers.sales._guardar_venta", _fallo)

    with TestClient(app) as client:
        response = client.post("/sales", json=_payload((1, 4)), headers=_auth())

    assert response.status_code == 502
    ventas, lineas = _persistido()
    assert ventas == [] and lineas == []

    salida = next(r for r in fake.requests if r.url.path == _SALIDA_PATH)
    reference = json.loads(salida.content)["reference"]
    compensaciones = [r for r in fake.requests if r.url.path == _MOVEMENTS_PATH]
    assert len(compensaciones) == 1
    assert json.loads(compensaciones[0].content) == {
        "product_id": 1,
        "movement_type": "entrada",
        "quantity": 4,
        "reason": "ajuste",
        "reference": reference,
    }


def test_crear_venta_422_items_duplicados(sales_db):
    fake = FakeInventory()
    fake.products = {1: _product(1, stock=10)}
    _usar_inventario(fake)

    with TestClient(app) as client:
        response = client.post("/sales", json=_payload((1, 1), (1, 2)), headers=_auth())

    assert response.status_code == 422
    ventas, _ = _persistido()
    assert ventas == []


def test_crear_venta_401_sin_token(sales_db):
    with TestClient(app) as client:
        response = client.post("/sales", json=_payload((1, 1)))
    assert response.status_code == 401


def test_crear_venta_403_rol_no_autorizado(sales_db):
    with TestClient(app) as client:
        response = client.post(
            "/sales", json=_payload((1, 1)), headers=_auth(role="invitado")
        )
    assert response.status_code == 403
