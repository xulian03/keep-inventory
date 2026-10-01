"""Fixtures compartidas de los tests de inventario (F-004).

Cada test apunta INVENTORY_DB a un SQLite temporal (fixture con tmp_path) y crea
las tablas con Base.metadata.create_all, sembrando proveedores, productos,
movimientos y órdenes de compra directamente con SQLAlchemy (sin seed.py).
"""

from collections.abc import Iterator

import pytest
from inventory import db
from inventory.models import (
    Base,
    Product,
    PurchaseOrder,
    PurchaseOrderItem,
    StockMovement,
    Supplier,
)

_CREATED_AT = "2026-10-01T00:00:00"
_FILLERS = 55


@pytest.fixture
def seeded_db(tmp_path, monkeypatch) -> Iterator[dict]:
    db_path = tmp_path / "inventory_test.db"
    monkeypatch.setenv("INVENTORY_DB", str(db_path))

    engine = db.get_engine()
    Base.metadata.create_all(engine)
    session = db.get_session_factory(engine)()

    supplier = Supplier(
        name="Proveedor Uno", contact_email="uno@test.com", lead_time_days=3
    )
    session.add(supplier)
    session.flush()

    def make_product(
        name: str,
        brand: str,
        category: str,
        subcategory: str,
        product_type: str,
        stock: int,
        min_threshold: int,
        excess_threshold: int,
        is_active: int,
        supplier_id: int | None,
    ) -> Product:
        product = Product(
            name=name,
            brand=brand,
            category=category,
            subcategory=subcategory,
            type=product_type,
            sale_price=1.0,
            market_price=2.0,
            rating=4.5,
            is_active=is_active,
            stock=stock,
            min_threshold=min_threshold,
            excess_threshold=excess_threshold,
            supplier_id=supplier_id,
            created_at=_CREATED_AT,
        )
        session.add(product)
        return product

    agotado = make_product(
        "Arroz Agotado", "MarcaA", "Alimentos", "Cereales", "Basico",
        0, 10, 100, 1, supplier.id,
    )
    bajo = make_product(
        "Leche Bajo", "MarcaB", "Lacteos", "Leche", "Fresco",
        5, 10, 100, 1, supplier.id,
    )
    disponible = make_product(
        "Pan Disponible", "MarcaA", "Panaderia", "Pan", "Fresco",
        50, 10, 100, 1, None,
    )
    exceso = make_product(
        "Aceite Exceso", "MarcaC", "Alimentos", "Aceites", "Basico",
        150, 10, 100, 1, None,
    )
    inactivo = make_product(
        "Producto Inactivo", "MarcaD", "Limpieza", "General", "Hogar",
        20, 10, 100, 0, None,
    )
    for index in range(_FILLERS):
        make_product(
            f"Relleno {index}", "MarcaR", "Relleno", "R", "Varios",
            50, 10, 100, 1, None,
        )

    session.flush()

    # Movimientos de ejemplo con fechas fijas para probar filtros y orden.
    movimientos = [
        StockMovement(
            product_id=disponible.id,
            movement_type="entrada",
            quantity=30,
            reason="compra",
            reference="po:1",
            created_at="2026-09-20T10:00:00",
        ),
        StockMovement(
            product_id=disponible.id,
            movement_type="salida",
            quantity=10,
            reason="venta",
            reference="venta:1",
            created_at="2026-09-25T15:30:00",
        ),
        StockMovement(
            product_id=disponible.id,
            movement_type="entrada",
            quantity=5,
            reason="ajuste",
            reference=None,
            created_at="2026-09-28T09:15:00",
        ),
        StockMovement(
            product_id=bajo.id,
            movement_type="entrada",
            quantity=5,
            reason="ajuste",
            reference=None,
            created_at="2026-09-22T08:00:00",
        ),
    ]
    session.add_all(movimientos)

    # Órdenes de compra con fechas fijas para probar filtros, totales y estados.
    def make_order(
        status: str,
        created_at: str,
        expected_date: str,
        items: list[tuple[Product, int, float]],
    ) -> PurchaseOrder:
        order = PurchaseOrder(
            supplier_id=supplier.id,
            status=status,
            expected_date=expected_date,
            created_at=created_at,
            received_at=None,
        )
        session.add(order)
        session.flush()
        for product, quantity, unit_cost in items:
            session.add(
                PurchaseOrderItem(
                    order_id=order.id,
                    product_id=product.id,
                    quantity=quantity,
                    unit_cost=unit_cost,
                )
            )
        return order

    po_borrador = make_order(
        "borrador",
        "2026-09-20T10:00:00",
        "2026-09-25T12:00:00",
        [(disponible, 2, 1.5), (bajo, 3, 2.0)],
    )
    po_enviada = make_order(
        "enviada",
        "2026-09-22T08:00:00",
        "2026-09-28T12:00:00",
        [(exceso, 4, 0.5)],
    )
    po_borrador2 = make_order(
        "borrador",
        "2026-09-25T15:30:00",
        "2026-10-01T12:00:00",
        [(disponible, 1, 10.0)],
    )

    session.commit()
    ids = {
        "supplier": supplier.id,
        "agotado": agotado.id,
        "bajo": bajo.id,
        "disponible": disponible.id,
        "exceso": exceso.id,
        "inactivo": inactivo.id,
        "total_productos": 5 + _FILLERS,
        "total_movimientos": len(movimientos),
        "movimientos_disponible": 3,
        "po_borrador": po_borrador.id,
        "po_enviada": po_enviada.id,
        "po_borrador2": po_borrador2.id,
        "po_borrador_total": 9.0,
        "po_enviada_total": 2.0,
        "po_borrador2_total": 10.0,
        "total_ordenes": 3,
    }
    session.close()
    engine.dispose()
    yield ids
