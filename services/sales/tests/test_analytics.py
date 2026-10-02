"""Tests de los helpers de analítica (F-005, paso 2).

Ejercitan `sales.analytics` directamente (sin TestClient) sobre la BD temporal
del conftest. La semilla son 4 ventas con valores calculables a mano, con fines
de semana incluidos para probar el plegado por semana y varias categorías.
"""

from datetime import date

from sales import db
from sales.analytics import (
    fold_daily_by_month,
    fold_daily_by_week,
    get_daily_buckets,
    get_daily_units_by_product,
    get_kpis,
    get_sales_by_category,
    get_top_products,
)
from sales.models import Sale, SaleItem


def _item(
    product_id: int,
    *,
    name: str,
    category: str,
    quantity: int,
    unit_price: float,
) -> dict:
    return {
        "product_id": product_id,
        "product_name": name,
        "category": category,
        "quantity": quantity,
        "unit_price": unit_price,
        "line_total": quantity * unit_price,
    }


def _insertar(sale_id: int, *, employee_id: int, created_at: str, items: list[dict]):
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


def _sembrar() -> None:
    # Lunes 2026-05-04.
    _insertar(
        1,
        employee_id=1,
        created_at="2026-05-04T10:00:00",
        items=[
            _item(1, name="Arroz", category="Alimentos", quantity=2, unit_price=1.5),
            _item(2, name="Leche", category="Lacteos", quantity=1, unit_price=2.0),
        ],
    )
    # Sábado 2026-05-09 (misma semana ISO que el lunes anterior).
    _insertar(
        2,
        employee_id=1,
        created_at="2026-05-09T15:00:00",
        items=[
            _item(1, name="Arroz", category="Alimentos", quantity=1, unit_price=1.5),
            _item(3, name="Jugo", category="Bebidas", quantity=4, unit_price=0.5),
        ],
    )
    # Lunes 2026-05-11 (semana siguiente).
    _insertar(
        3,
        employee_id=2,
        created_at="2026-05-11T09:00:00",
        items=[
            _item(1, name="Arroz", category="Alimentos", quantity=3, unit_price=1.5),
        ],
    )
    _insertar(
        4,
        employee_id=2,
        created_at="2026-05-12T20:00:00",
        items=[
            _item(2, name="Leche", category="Lacteos", quantity=2, unit_price=2.0),
        ],
    )


def _session():
    return db.get_session_factory(db.get_engine())()


def test_kpis_rango_vacio_devuelve_ceros(sales_db):
    session = _session()
    try:
        kpis = get_kpis(session, "2026-06-01", "2026-06-30")
    finally:
        session.close()

    assert kpis == {"total": 0.0, "transactions": 0, "avg_ticket": 0.0, "units": 0}


def test_kpis_con_valores_calculados_a_mano(sales_db):
    _sembrar()
    session = _session()
    try:
        kpis = get_kpis(session, "2026-05-01", "2026-05-31")
    finally:
        session.close()

    # totales: 5.0 + 3.5 + 4.5 + 4.0 = 17.0 ; unidades 13 ; 4 ventas.
    assert kpis["total"] == 17.0
    assert kpis["transactions"] == 4
    assert kpis["units"] == 13
    assert kpis["avg_ticket"] == 4.25


def test_kpis_subrango(sales_db):
    _sembrar()
    session = _session()
    try:
        kpis = get_kpis(session, "2026-05-04", "2026-05-09")
    finally:
        session.close()

    assert kpis["total"] == 8.5
    assert kpis["transactions"] == 2
    assert kpis["units"] == 8
    assert kpis["avg_ticket"] == 4.25


def test_buckets_diarios_solo_dias_con_ventas(sales_db):
    _sembrar()
    session = _session()
    try:
        rows = get_daily_buckets(session, "2026-05-01", "2026-05-31")
    finally:
        session.close()

    assert [row["bucket"] for row in rows] == [
        "2026-05-04",
        "2026-05-09",
        "2026-05-11",
        "2026-05-12",
    ]
    assert rows[0] == {
        "bucket": "2026-05-04",
        "total": 5.0,
        "units": 3,
        "transactions": 1,
    }
    assert rows[1]["total"] == 3.5
    assert rows[1]["units"] == 5
    assert rows[3]["total"] == 4.0


def test_buckets_diarios_filtra_por_categoria(sales_db):
    _sembrar()
    session = _session()
    try:
        rows = get_daily_buckets(session, "2026-05-01", "2026-05-31", category="Bebidas")
    finally:
        session.close()

    assert rows == [
        {"bucket": "2026-05-09", "total": 2.0, "units": 4, "transactions": 1}
    ]


def test_plegado_por_semana_lunes_iso(sales_db):
    _sembrar()
    session = _session()
    try:
        rows = get_daily_buckets(session, "2026-05-01", "2026-05-31")
    finally:
        session.close()

    folded = fold_daily_by_week(rows)

    assert [row["bucket"] for row in folded] == ["2026-05-04", "2026-05-11"]
    assert folded[0] == {
        "bucket": "2026-05-04",
        "total": 8.5,
        "units": 8,
        "transactions": 2,
    }
    assert folded[1] == {
        "bucket": "2026-05-11",
        "total": 8.5,
        "units": 5,
        "transactions": 2,
    }


def test_plegado_por_mes(sales_db):
    _sembrar()
    session = _session()
    try:
        rows = get_daily_buckets(session, "2026-05-01", "2026-05-31")
    finally:
        session.close()

    folded = fold_daily_by_month(rows)

    assert folded == [
        {"bucket": "2026-05", "total": 17.0, "units": 13, "transactions": 4}
    ]


def test_ventas_por_categoria_desc_por_total(sales_db):
    _sembrar()
    session = _session()
    try:
        rows = get_sales_by_category(session, "2026-05-01", "2026-05-31")
    finally:
        session.close()

    assert rows == [
        {"category": "Alimentos", "total": 9.0, "units": 6},
        {"category": "Lacteos", "total": 6.0, "units": 3},
        {"category": "Bebidas", "total": 2.0, "units": 4},
    ]


def test_top_productos_desc_con_limit(sales_db):
    _sembrar()
    session = _session()
    try:
        rows = get_top_products(session, "2026-05-01", "2026-05-31", limit=2)
    finally:
        session.close()

    assert rows == [
        {
            "product_id": 1,
            "product_name": "Arroz",
            "category": "Alimentos",
            "units": 6,
            "total": 9.0,
        },
        {
            "product_id": 2,
            "product_name": "Leche",
            "category": "Lacteos",
            "units": 3,
            "total": 6.0,
        },
    ]


def test_top_productos_filtra_por_categoria(sales_db):
    _sembrar()
    session = _session()
    try:
        rows = get_top_products(
            session, "2026-05-01", "2026-05-31", category="Bebidas", limit=10
        )
    finally:
        session.close()

    assert rows == [
        {
            "product_id": 3,
            "product_name": "Jugo",
            "category": "Bebidas",
            "units": 4,
            "total": 2.0,
        }
    ]


def test_serie_diaria_incluye_ceros_y_longitud(sales_db):
    _sembrar()
    session = _session()
    try:
        series = get_daily_units_by_product(
            session, product_ids=[1, 2, 3, 4], days=7, today=date(2026, 5, 12)
        )
    finally:
        session.close()

    assert set(series) == {1, 2, 3, 4}
    # Días: 06, 07, 08, 09, 10, 11, 12 de mayo.
    assert series[1] == [0, 0, 0, 1, 0, 3, 0]
    assert series[2] == [0, 0, 0, 0, 0, 0, 2]
    assert series[3] == [0, 0, 0, 4, 0, 0, 0]
    assert series[4] == [0] * 7
    assert len(series[1]) == 7


def test_serie_diaria_default_120_dias(sales_db):
    _sembrar()
    session = _session()
    try:
        series = get_daily_units_by_product(
            session, product_ids=[1], today=date(2026, 5, 12)
        )
    finally:
        session.close()

    serie = series[1]
    assert len(serie) == 120
    # Ventana 2026-01-13 .. 2026-05-12.
    assert serie[116] == 1  # 2026-05-09
    assert serie[118] == 3  # 2026-05-11
    assert serie[119] == 0  # 2026-05-12
