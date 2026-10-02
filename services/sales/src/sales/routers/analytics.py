"""Endpoints de analítica (F-005, pasos 3-4).

- `GET /analytics/kpis`: KPIs de ventas con SQL local sobre el rango pedido y el
  período anterior de igual largo (delta %); el estado del inventario se agrega
  recorriendo `GET /products?is_active=1` (page_size=100) reenviando el JWT del
  usuario. Si Inventario no responde se responde 502.
- `GET /analytics/sales-trend` (day|week|month), `GET /analytics/sales-by-category`
  y `GET /analytics/top-products`: sólo SQL local (sin llamar a Inventario).
- `GET /analytics/purchases-summary`: recorre `GET /purchase-orders` (páginas de
  100) y `GET /suppliers`; el rango opcional filtra `received_at` (default: todas)
  y `counts_by_status` es siempre sobre todas las órdenes.

Todos son admin-only. Los endpoints de ventas comparten la regla de rangos de
`_resolve_period` (extremo que falta → hoy / hoy−29; 422 si from > to); en
purchases-summary faltar un extremo no inventa fechas.
"""

from datetime import date, datetime, timedelta
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from sales import analytics
from sales.deps import get_session, parse_date_bound
from sales.inventory_client import (
    InventoryClient,
    InventoryUnavailable,
    get_inventory_client,
)
from sales.rbac import require_roles

router = APIRouter(tags=["analytics"])

_bearer = HTTPBearer(auto_error=False)

_STATE_KEYS = ("agotado", "bajo", "disponible", "exceso")
_ORDER_STATUS_KEYS = ("borrador", "enviada", "recibida", "cancelada")
_PAGE_SIZE = 100
_DAYS_DEFAULT = 30


def get_access_token(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> str:
    if credentials is None:
        raise HTTPException(status_code=401, detail="No autenticado")
    return credentials.credentials


def _to_date(value: str) -> date:
    """Valida el ISO y devuelve su fecha (ignora la hora si la trae)."""
    bound = parse_date_bound(value, end=False)
    if bound is None:  # pragma: no cover - parse_date_bound no devuelve None aquí
        raise HTTPException(status_code=422, detail="Fecha inválida")
    return datetime.fromisoformat(bound).date()


def _resolve_period(date_from: str | None, date_to: str | None) -> tuple[date, date]:
    """Período inclusivo [from, to]; default: últimos 30 días hasta hoy."""
    to = _to_date(date_to) if date_to is not None else date.today()
    if date_from is not None:
        from_ = _to_date(date_from)
    else:
        from_ = to - timedelta(days=_DAYS_DEFAULT - 1)
    if from_ > to:
        raise HTTPException(status_code=422, detail="Rango de fechas inválido")
    return from_, to


def _previous_period(from_: date, to: date) -> tuple[date, date]:
    """Período inmediatamente anterior de igual largo, inclusivo."""
    length = (to - from_).days + 1
    prev_to = from_ - timedelta(days=1)
    prev_from = prev_to - timedelta(days=length - 1)
    return prev_from, prev_to


def _delta_pct(actual: float, previous: float, has_previous: bool) -> float | None:
    """(act−ant)/ant·100 a 1 decimal; null si no hubo transacciones antes."""
    if not has_previous or previous == 0:
        return None
    return round((actual - previous) / previous * 100, 1)


def _inventory_summary(client: InventoryClient, token: str) -> dict:
    """Recorre todas las páginas activas y agrega valor y estados."""
    value = 0.0
    products_total = 0
    counts = {key: 0 for key in _STATE_KEYS}
    page = 1
    while True:
        envelope = client.get_products_page(
            token, page=page, page_size=_PAGE_SIZE, is_active=True
        )
        if page == 1:
            products_total = int(envelope.get("total", 0))
        items = envelope.get("items", [])
        for product in items:
            value += float(product.get("stock", 0)) * float(
                product.get("sale_price", 0)
            )
            state = product.get("state")
            if state in counts:
                counts[state] += 1
        if len(items) < _PAGE_SIZE:
            break
        page += 1
    return {"value": value, "products_total": products_total, "counts": counts}


@router.get("/analytics/kpis")
def get_kpis(
    date_from: str | None = None,
    date_to: str | None = None,
    user: dict = Depends(require_roles("admin")),
    token: str = Depends(get_access_token),
    session: Session = Depends(get_session),
    client: InventoryClient = Depends(get_inventory_client),
) -> dict:
    from_, to = _resolve_period(date_from, date_to)
    prev_from, prev_to = _previous_period(from_, to)

    current = analytics.get_kpis(session, from_.isoformat(), to.isoformat())
    previous = analytics.get_kpis(
        session, prev_from.isoformat(), prev_to.isoformat()
    )
    has_previous = previous["transactions"] > 0

    try:
        inventory = _inventory_summary(client, token)
    except InventoryUnavailable as exc:
        raise HTTPException(status_code=502, detail="Inventario no disponible") from exc

    return {
        "period": {"from": from_.isoformat(), "to": to.isoformat()},
        "sales": {
            "total": current["total"],
            "transactions": current["transactions"],
            "avg_ticket": current["avg_ticket"],
            "units": current["units"],
            "delta_pct": {
                "total": _delta_pct(
                    current["total"], previous["total"], has_previous
                ),
                "transactions": _delta_pct(
                    current["transactions"], previous["transactions"], has_previous
                ),
                "avg_ticket": _delta_pct(
                    current["avg_ticket"], previous["avg_ticket"], has_previous
                ),
                "units": _delta_pct(
                    current["units"], previous["units"], has_previous
                ),
            },
        },
        "inventory": inventory,
    }


@router.get("/analytics/sales-trend")
def get_sales_trend(
    group_by: Literal["day", "week", "month"] = "day",
    date_from: str | None = None,
    date_to: str | None = None,
    category: str | None = None,
    user: dict = Depends(require_roles("admin")),
    session: Session = Depends(get_session),
) -> dict:
    from_, to = _resolve_period(date_from, date_to)
    rows = analytics.get_daily_buckets(
        session, from_.isoformat(), to.isoformat(), category=category
    )
    if group_by == "week":
        points = analytics.fold_daily_by_week(rows)
    elif group_by == "month":
        points = analytics.fold_daily_by_month(rows)
    else:
        points = rows
    return {
        "group_by": group_by,
        "from": from_.isoformat(),
        "to": to.isoformat(),
        "points": points,
    }


@router.get("/analytics/sales-by-category")
def get_sales_by_category(
    date_from: str | None = None,
    date_to: str | None = None,
    user: dict = Depends(require_roles("admin")),
    session: Session = Depends(get_session),
) -> dict:
    from_, to = _resolve_period(date_from, date_to)
    items = analytics.get_sales_by_category(
        session, from_.isoformat(), to.isoformat()
    )
    return {"items": items}


@router.get("/analytics/top-products")
def get_top_products(
    date_from: str | None = None,
    date_to: str | None = None,
    category: str | None = None,
    limit: int = Query(10, ge=1, le=50),
    user: dict = Depends(require_roles("admin")),
    session: Session = Depends(get_session),
) -> dict:
    from_, to = _resolve_period(date_from, date_to)
    items = analytics.get_top_products(
        session,
        from_.isoformat(),
        to.isoformat(),
        category=category,
        limit=limit,
    )
    return {"items": items}


def _day_of(value: str | None) -> date | None:
    """Fecha de un ISO-8601 (ignora la hora); None si falta o es inválido."""
    if not value:
        return None
    try:
        return datetime.fromisoformat(value).date()
    except ValueError:
        return None


def _received_in_range(
    received_at: str | None, from_: date | None, to: date | None
) -> bool:
    """True si received_at cae dentro del rango inclusivo (extremos opcionales)."""
    day = _day_of(received_at)
    if day is None:
        return False
    if from_ is not None and day < from_:
        return False
    if to is not None and day > to:
        return False
    return True


@router.get("/analytics/purchases-summary")
def get_purchases_summary(
    date_from: str | None = None,
    date_to: str | None = None,
    user: dict = Depends(require_roles("admin")),
    token: str = Depends(get_access_token),
    client: InventoryClient = Depends(get_inventory_client),
) -> dict:
    """Resumen de compras; el rango filtra `received_at` (default: todas)."""
    from_ = _to_date(date_from) if date_from is not None else None
    to = _to_date(date_to) if date_to is not None else None
    if from_ is not None and to is not None and from_ > to:
        raise HTTPException(status_code=422, detail="Rango de fechas inválido")

    try:
        orders = client.get_all_purchase_orders(token)
        suppliers = client.get_suppliers(token)
    except InventoryUnavailable as exc:
        raise HTTPException(status_code=502, detail="Inventario no disponible") from exc

    counts = {key: 0 for key in _ORDER_STATUS_KEYS}
    for order in orders:
        status = order.get("status")
        if status in counts:
            counts[status] += 1

    received = [
        order
        for order in orders
        if order.get("status") == "recibida"
        and _received_in_range(order.get("received_at"), from_, to)
    ]

    spend = 0.0
    by_month: dict[str, dict] = {}
    by_supplier: dict[int, dict] = {}
    names = {supplier["id"]: supplier.get("name") for supplier in suppliers}
    for order in received:
        total = float(order.get("total") or 0)
        spend += total

        month = (order.get("received_at") or "")[:7]
        month_bucket = by_month.setdefault(
            month, {"month": month, "orders": 0, "spend": 0.0}
        )
        month_bucket["orders"] += 1
        month_bucket["spend"] += total

        supplier_id = order.get("supplier_id")
        supplier_bucket = by_supplier.setdefault(
            supplier_id,
            {
                "supplier_id": supplier_id,
                "supplier_name": names.get(supplier_id),
                "orders": 0,
                "spend": 0.0,
            },
        )
        supplier_bucket["orders"] += 1
        supplier_bucket["spend"] += total

    return {
        "totals": {
            "orders_received": len(received),
            "spend_received": spend,
            "counts_by_status": counts,
        },
        "by_month": sorted(by_month.values(), key=lambda bucket: bucket["month"]),
        "by_supplier": sorted(
            by_supplier.values(), key=lambda bucket: bucket["spend"], reverse=True
        ),
    }
