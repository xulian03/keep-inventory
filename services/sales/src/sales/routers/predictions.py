"""Endpoint de predicciones de demanda (F-005, paso 6).

`GET /predictions` (admin-only) devuelve, por página, una llamada a
`GET /products?page&category&is_active=1` reenviando el JWT del usuario y la
predicción local de cada uno de sus productos: la serie diaria de 120 días
(ceros incluidos) de esos ids sale de `analytics.get_daily_units_by_product` y
el modelo de `forecasting.predict_demand`. Si Inventario no responde se devuelve
502; una página sin ítems devuelve `items: []`.
"""

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from sales import analytics, forecasting
from sales.deps import get_session
from sales.inventory_client import (
    InventoryClient,
    InventoryUnavailable,
    get_inventory_client,
)
from sales.rbac import require_roles

router = APIRouter(tags=["predictions"])

_bearer = HTTPBearer(auto_error=False)

_DAYS_SERIES = 120
_PAGE_SIZE_DEFAULT = 50
_PAGE_SIZE_MAX = 100


def get_access_token(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> str:
    if credentials is None:
        raise HTTPException(status_code=401, detail="No autenticado")
    return credentials.credentials


def _predictions_for(
    session: Session, products: list[dict], hoy: date
) -> list[dict]:
    """Predice cada producto de la página con su serie diaria local de 120 días."""
    series = analytics.get_daily_units_by_product(
        session,
        [product["id"] for product in products],
        days=_DAYS_SERIES,
        today=hoy,
    )

    items = []
    for product in products:
        stock = int(product.get("stock", 0))
        min_threshold = int(product.get("min_threshold", 0))
        forecast = forecasting.predict_demand(
            series.get(product["id"], [0] * _DAYS_SERIES),
            stock=stock,
            min_threshold=min_threshold,
            hoy=hoy,
        )
        items.append(
            {
                "product_id": product["id"],
                "product_name": product.get("name"),
                "category": product.get("category"),
                "stock": stock,
                "min_threshold": min_threshold,
                "state": product.get("state"),
                "method": forecast.method,
                "daily_demand": forecast.daily_demand,
                "trend": forecast.trend,
                "stockout_date": (
                    forecast.stockout_date.isoformat()
                    if forecast.stockout_date is not None
                    else None
                ),
                "demand_30d": forecast.demand_30d,
                "suggested_reorder": forecast.suggested_reorder,
            }
        )
    return items


@router.get("/predictions")
def get_predictions(
    page: int = Query(1, ge=1),
    page_size: int = Query(_PAGE_SIZE_DEFAULT, ge=1, le=_PAGE_SIZE_MAX),
    category: str | None = None,
    user: dict = Depends(require_roles("admin")),
    token: str = Depends(get_access_token),
    session: Session = Depends(get_session),
    client: InventoryClient = Depends(get_inventory_client),
) -> dict:
    try:
        envelope = client.get_products_page(
            token,
            page=page,
            page_size=page_size,
            category=category,
            is_active=True,
        )
    except InventoryUnavailable as exc:
        raise HTTPException(
            status_code=502, detail="Inventario no disponible"
        ) from exc

    products = envelope.get("items", [])
    return {
        "items": _predictions_for(session, products, date.today()),
        "total": int(envelope.get("total", 0)),
        "page": page,
        "page_size": page_size,
    }
