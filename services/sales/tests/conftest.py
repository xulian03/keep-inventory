"""Fixtures de los tests de Ventas (F-004, paso 7; F-005, paso 3).

Cada test apunta SALES_DB a un SQLite temporal y crea las tablas con
Base.metadata.create_all. Inventario no se levanta: los tests sobreescriben la
dependencia get_inventory_client con un InventoryClient sobre httpx.MockTransport.

`FakeInventory`/`fake_inventory` sirven `GET /products?is_active=...` paginado
con stock/sale_price/state variados (F-005), `GET /purchase-orders` paginado y
`GET /suppliers` (F-005, paso 5).
"""

from collections.abc import Iterator

import httpx
import pytest
from sales import db
from sales.inventory_client import InventoryClient, get_inventory_client
from sales.main import app
from sales.models import Base


class FakeInventory:
    """Handler de httpx.MockTransport que simula los endpoints de Inventario."""

    def __init__(self) -> None:
        self.products: list[dict] = []
        self.purchase_orders: list[dict] = []
        self.suppliers: list[dict] = []
        self.fail = False
        self.requests: list[httpx.Request] = []

    def handler(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        if self.fail:
            return httpx.Response(500, json={"detail": "inventario caído"})
        if request.url.path == "/products":
            return self._products(request)
        if request.url.path == "/purchase-orders":
            return self._page(request, self.purchase_orders)
        if request.url.path == "/suppliers":
            return httpx.Response(200, json=list(self.suppliers))
        return httpx.Response(404, json={"detail": "no encontrado"})

    def _products(self, request: httpx.Request) -> httpx.Response:
        params = request.url.params
        items = list(self.products)
        if params.get("is_active") is not None:
            active = params.get("is_active").lower() in ("1", "true", "yes")
            items = [p for p in items if bool(p.get("is_active", True)) == active]
        category = params.get("category")
        if category is not None:
            items = [p for p in items if p.get("category") == category]
        return self._page(request, items)

    @staticmethod
    def _page(request: httpx.Request, items: list[dict]) -> httpx.Response:
        params = request.url.params
        page = int(params.get("page", "1"))
        page_size = int(params.get("page_size", "50"))
        total = len(items)
        start = (page - 1) * page_size
        return httpx.Response(
            200,
            json={
                "items": items[start : start + page_size],
                "total": total,
                "page": page,
                "page_size": page_size,
            },
        )


@pytest.fixture
def sales_db(tmp_path, monkeypatch) -> Iterator[str]:
    db_path = tmp_path / "sales_test.db"
    monkeypatch.setenv("SALES_DB", str(db_path))
    engine = db.get_engine()
    Base.metadata.create_all(engine)
    engine.dispose()
    yield str(db_path)


@pytest.fixture
def fake_inventory() -> Iterator[FakeInventory]:
    fake = FakeInventory()
    client = InventoryClient(
        base_url="http://inventario.test",
        transport=httpx.MockTransport(fake.handler),
    )
    app.dependency_overrides[get_inventory_client] = lambda: client
    yield fake
    client.close()


@pytest.fixture(autouse=True)
def _limpiar_overrides() -> Iterator[None]:
    yield
    app.dependency_overrides.clear()
