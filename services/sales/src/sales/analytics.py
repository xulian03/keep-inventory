"""Consultas de analítica sobre la BD local de Ventas (F-005, paso 2).

Helpers de SQL puro sobre `Sale`/`SaleItem` (SQLite local). No usan FastAPI,
httpx ni Inventory: sólo sesión SQLAlchemy y los filtros ISO TEXT de
`Sale.created_at` / `SaleItem.category`, igual que `routers/sales.py`.

Los buckets diarios se devuelven tal cual (sólo días con ventas); el plegado a
semana (lunes ISO) o mes ('YYYY-MM') se hace en Python con
`fold_daily_by_week` / `fold_daily_by_month`.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from datetime import date, datetime, time, timedelta

from sqlalchemy import func
from sqlalchemy.orm import Query, Session

from sales.deps import parse_date_bound
from sales.models import Sale, SaleItem


def _apply_range(
    query: Query,
    date_from: str | None,
    date_to: str | None,
) -> Query:
    """Aplica los filtros ISO TEXT [date_from, date_to] sobre Sale.created_at."""
    date_from_bound = parse_date_bound(date_from, end=False)
    date_to_bound = parse_date_bound(date_to, end=True)
    if date_from_bound is not None:
        query = query.filter(Sale.created_at >= date_from_bound)
    if date_to_bound is not None:
        query = query.filter(Sale.created_at <= date_to_bound)
    return query


def get_kpis(
    session: Session,
    date_from: str | None = None,
    date_to: str | None = None,
) -> dict:
    """KPIs del rango: total, transacciones, ticket medio y unidades.

    `avg_ticket` = total / transacciones (0.0 si no hay ventas).
    """
    row = _apply_range(
        session.query(
            func.coalesce(func.sum(SaleItem.line_total), 0.0),
            func.count(func.distinct(Sale.id)),
            func.coalesce(func.sum(SaleItem.quantity), 0),
        ).join(Sale, SaleItem.sale_id == Sale.id),
        date_from,
        date_to,
    ).one()

    total = float(row[0] or 0.0)
    transactions = int(row[1] or 0)
    units = int(row[2] or 0)
    avg_ticket = total / transactions if transactions else 0.0
    return {
        "total": total,
        "transactions": transactions,
        "avg_ticket": avg_ticket,
        "units": units,
    }


def get_daily_units_by_product(
    session: Session,
    product_ids: Iterable[int] | None = None,
    days: int = 120,
    today: date | None = None,
) -> dict[int, list[int]]:
    """Serie diaria de unidades por product_id, con ceros, hasta hoy.

    Devuelve `dict[int, list[int]]` con exactamente `days` posiciones por
    producto (el índice 0 es el día más antiguo). Si se pasan `product_ids`, la
    salida incluye esos ids aunque no tengan ventas (serie de ceros).
    """
    end = today or date.today()
    start = end - timedelta(days=days - 1)
    start_iso = datetime.combine(start, time.min).isoformat()
    end_iso = datetime.combine(end, time.max).isoformat()

    bucket = func.substr(Sale.created_at, 1, 10)
    rows = (
        session.query(
            SaleItem.product_id,
            bucket.label("bucket"),
            func.sum(SaleItem.quantity),
        )
        .join(Sale, SaleItem.sale_id == Sale.id)
        .filter(Sale.created_at >= start_iso, Sale.created_at <= end_iso)
        .group_by(SaleItem.product_id, bucket)
        .all()
    )

    requested = list(product_ids) if product_ids is not None else None
    series: dict[int, list[int]] = {pid: [0] * days for pid in requested or []}
    for product_id, day, quantity in rows:
        if product_id not in series:
            if requested is not None:
                continue
            series[product_id] = [0] * days
        index = (date.fromisoformat(day) - start).days
        if 0 <= index < days:
            series[product_id][index] = int(quantity or 0)
    return series


def get_daily_buckets(
    session: Session,
    date_from: str | None = None,
    date_to: str | None = None,
    category: str | None = None,
) -> list[dict]:
    """Buckets por DÍA del rango, sólo con días que tengan ventas.

    Cada fila es {bucket: 'YYYY-MM-DD', total, units, transactions}.
    """
    bucket = func.substr(Sale.created_at, 1, 10)
    query = (
        session.query(
            bucket.label("bucket"),
            func.sum(SaleItem.line_total),
            func.sum(SaleItem.quantity),
            func.count(func.distinct(Sale.id)),
        )
        .join(Sale, SaleItem.sale_id == Sale.id)
        .group_by(bucket)
        .order_by(bucket)
    )
    if category is not None:
        query = query.filter(SaleItem.category == category)
    query = _apply_range(query, date_from, date_to)
    return [
        {
            "bucket": row[0],
            "total": float(row[1] or 0.0),
            "units": int(row[2] or 0),
            "transactions": int(row[3] or 0),
        }
        for row in query.all()
    ]


def _fold_daily(
    rows: list[dict],
    key_fn: Callable[[date], str],
) -> list[dict]:
    """Agrupa filas diarias con `key_fn` y suma total/units/transactions."""
    folded: dict[str, dict] = {}
    for row in rows:
        key = key_fn(date.fromisoformat(row["bucket"]))
        agg = folded.setdefault(
            key,
            {"bucket": key, "total": 0.0, "units": 0, "transactions": 0},
        )
        agg["total"] += row["total"]
        agg["units"] += row["units"]
        agg["transactions"] += row["transactions"]
    return sorted(folded.values(), key=lambda item: item["bucket"])


def fold_daily_by_week(rows: list[dict]) -> list[dict]:
    """Pliega filas diarias al lunes ISO de su semana ('YYYY-MM-DD')."""
    return _fold_daily(
        rows, lambda day: (day - timedelta(days=day.weekday())).isoformat()
    )


def fold_daily_by_month(rows: list[dict]) -> list[dict]:
    """Pliega filas diarias al mes de su fecha ('YYYY-MM')."""
    return _fold_daily(rows, lambda day: f"{day.year:04d}-{day.month:02d}")


def get_sales_by_category(
    session: Session,
    date_from: str | None = None,
    date_to: str | None = None,
) -> list[dict]:
    """Ventas por categoría del rango, desc por total.

    Cada fila es {category, total, units}.
    """
    query = (
        session.query(
            SaleItem.category,
            func.sum(SaleItem.line_total),
            func.sum(SaleItem.quantity),
        )
        .join(Sale, SaleItem.sale_id == Sale.id)
        .group_by(SaleItem.category)
        .order_by(func.sum(SaleItem.line_total).desc(), SaleItem.category.asc())
    )
    query = _apply_range(query, date_from, date_to)
    return [
        {
            "category": row[0],
            "total": float(row[1] or 0.0),
            "units": int(row[2] or 0),
        }
        for row in query.all()
    ]


def get_top_products(
    session: Session,
    date_from: str | None = None,
    date_to: str | None = None,
    category: str | None = None,
    limit: int = 10,
) -> list[dict]:
    """Top productos por total del rango, desc por total, recortado a `limit`.

    Cada fila es {product_id, product_name, category, units, total}.
    """
    query = (
        session.query(
            SaleItem.product_id,
            SaleItem.product_name,
            SaleItem.category,
            func.sum(SaleItem.quantity),
            func.sum(SaleItem.line_total),
        )
        .join(Sale, SaleItem.sale_id == Sale.id)
        .group_by(SaleItem.product_id, SaleItem.product_name, SaleItem.category)
        .order_by(
            func.sum(SaleItem.line_total).desc(), SaleItem.product_id.asc()
        )
    )
    if category is not None:
        query = query.filter(SaleItem.category == category)
    query = _apply_range(query, date_from, date_to)
    query = query.limit(limit)
    return [
        {
            "product_id": row[0],
            "product_name": row[1],
            "category": row[2],
            "units": int(row[3] or 0),
            "total": float(row[4] or 0.0),
        }
        for row in query.all()
    ]
