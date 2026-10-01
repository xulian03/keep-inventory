"""Fixtures de los tests de Ventas (F-004, paso 7).

Cada test apunta SALES_DB a un SQLite temporal y crea las tablas con
Base.metadata.create_all. Inventario no se levanta: los tests sobreescriben la
dependencia get_inventory_client con un InventoryClient sobre httpx.MockTransport.
"""

from collections.abc import Iterator

import pytest
from sales import db
from sales.main import app
from sales.models import Base


@pytest.fixture
def sales_db(tmp_path, monkeypatch) -> Iterator[str]:
    db_path = tmp_path / "sales_test.db"
    monkeypatch.setenv("SALES_DB", str(db_path))
    engine = db.get_engine()
    Base.metadata.create_all(engine)
    engine.dispose()
    yield str(db_path)


@pytest.fixture(autouse=True)
def _limpiar_overrides() -> Iterator[None]:
    yield
    app.dependency_overrides.clear()
