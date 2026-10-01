from datetime import datetime
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from sales.deps import get_session, parse_date_bound
from sales.inventory_client import (
    InventoryClient,
    InventoryConflict,
    InventoryUnavailable,
    get_inventory_client,
)
from sales.models import Sale, SaleItem
from sales.rbac import get_current_user, require_roles
from sales.schemas import (
    SaleCreate,
    SaleCreatedOut,
    SaleItemOut,
    SaleOut,
    SalePage,
    SaleStockOut,
)

router = APIRouter(tags=["sales"])

_bearer = HTTPBearer(auto_error=False)


def get_access_token(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> str:
    if credentials is None:
        raise HTTPException(status_code=401, detail="No autenticado")
    return credentials.credentials


def _now_iso() -> str:
    """ISO-8601 naive con segundos, igual que seed.py y los movimientos."""
    return datetime.now().replace(tzinfo=None).isoformat(timespec="seconds")


def _guardar_venta(
    session: Session,
    employee_id: int,
    lineas: list[dict],
    total: float,
) -> tuple[Sale, list[SaleItem]]:
    """Persiste la venta y sus líneas denormalizadas (ARCH §4.3)."""
    sale = Sale(employee_id=employee_id, total=total, created_at=_now_iso())
    session.add(sale)
    session.flush()
    items: list[SaleItem] = []
    for linea in lineas:
        item = SaleItem(sale_id=sale.id, **linea)
        session.add(item)
        items.append(item)
    session.flush()
    session.commit()
    return sale, items


def _compensar(
    client: InventoryClient, lineas: list[dict], reference: str, token: str
) -> None:
    """Revierte el descuento con entradas reason=ajuste (ARCH §6.2)."""
    for linea in lineas:
        try:
            client.registrar_entrada_ajuste(
                linea["product_id"], linea["quantity"], reference, token
            )
        except InventoryUnavailable:
            # Se intenta compensar cada ítem; si Inventario falla igual se
            # responde 502 (la compensación es best-effort).
            continue


def _item_out(item: SaleItem) -> SaleItemOut:
    return SaleItemOut(
        id=item.id,
        product_id=item.product_id,
        product_name=item.product_name,
        category=item.category,
        quantity=item.quantity,
        unit_price=item.unit_price,
        line_total=item.line_total,
    )


def _to_out(sale: Sale, items: list[SaleItem]) -> SaleOut:
    return SaleOut(
        id=sale.id,
        employee_id=sale.employee_id,
        total=sale.total,
        created_at=sale.created_at,
        items=[_item_out(item) for item in items],
    )


@router.get("/sales", response_model=SalePage)
def list_sales(
    product_id: int | None = None,
    category: str | None = None,
    employee_id: int | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    user: dict = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> SalePage:
    query = session.query(Sale)
    if product_id is not None:
        query = query.filter(
            Sale.id.in_(
                session.query(SaleItem.sale_id).filter(
                    SaleItem.product_id == product_id
                )
            )
        )
    if category is not None:
        query = query.filter(
            Sale.id.in_(
                session.query(SaleItem.sale_id).filter(SaleItem.category == category)
            )
        )
    if employee_id is not None:
        query = query.filter(Sale.employee_id == employee_id)
    date_from_bound = parse_date_bound(date_from, end=False)
    date_to_bound = parse_date_bound(date_to, end=True)
    if date_from_bound is not None:
        query = query.filter(Sale.created_at >= date_from_bound)
    if date_to_bound is not None:
        query = query.filter(Sale.created_at <= date_to_bound)
    query = query.order_by(Sale.created_at.desc(), Sale.id.desc())

    total = query.count()
    sales = query.offset((page - 1) * page_size).limit(page_size).all()

    items_by_sale: dict[int, list[SaleItem]] = {sale.id: [] for sale in sales}
    if sales:
        sale_ids = list(items_by_sale)
        for item in (
            session.query(SaleItem)
            .filter(SaleItem.sale_id.in_(sale_ids))
            .order_by(SaleItem.id.asc())
            .all()
        ):
            items_by_sale[item.sale_id].append(item)

    return SalePage(
        items=[_to_out(sale, items_by_sale[sale.id]) for sale in sales],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/sales/{sale_id}", response_model=SaleOut)
def get_sale(
    sale_id: int,
    user: dict = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> SaleOut:
    sale = session.get(Sale, sale_id)
    if sale is None:
        raise HTTPException(status_code=404, detail="Venta no encontrada")
    items = (
        session.query(SaleItem)
        .filter(SaleItem.sale_id == sale_id)
        .order_by(SaleItem.id.asc())
        .all()
    )
    return _to_out(sale, items)


@router.post("/sales", response_model=SaleCreatedOut, status_code=201)
def create_sale(
    payload: SaleCreate,
    user: dict = Depends(require_roles("empleado", "admin")),
    token: str = Depends(get_access_token),
    session: Session = Depends(get_session),
    client: InventoryClient = Depends(get_inventory_client),
) -> SaleCreatedOut:
    product_ids = [item.product_id for item in payload.items]

    # 1) Catálogo: existencia, is_active y stock suficiente.
    try:
        products = client.get_products(product_ids, token)
    except InventoryUnavailable as exc:
        raise HTTPException(status_code=502, detail="Inventario no disponible") from exc

    catalog = {product["id"]: product for product in products}
    for item in payload.items:
        product = catalog.get(item.product_id)
        if product is None:
            raise HTTPException(status_code=404, detail="Producto no encontrado")
        if not product["is_active"]:
            raise HTTPException(status_code=422, detail="Producto inactivo")
        if product["stock"] < item.quantity:
            raise HTTPException(status_code=422, detail="Stock insuficiente")

    # 2) Descuento atómico en Inventario (todo o nada; 409 sin descontar).
    reference = f"venta:{uuid4()}"
    salida_items = [
        {"product_id": item.product_id, "quantity": item.quantity}
        for item in payload.items
    ]
    try:
        salida = client.descontar_por_venta(reference, salida_items, token)
    except InventoryConflict as exc:
        raise HTTPException(status_code=409, detail="Stock insuficiente") from exc
    except InventoryUnavailable as exc:
        raise HTTPException(status_code=502, detail="Inventario no disponible") from exc

    # 3) Guardado local con datos denormalizados; total = Σ qty×unit_price.
    lineas = []
    for item in payload.items:
        product = catalog[item.product_id]
        line_total = item.quantity * product["sale_price"]
        lineas.append(
            {
                "product_id": item.product_id,
                "product_name": product["name"],
                "category": product["category"],
                "quantity": item.quantity,
                "unit_price": product["sale_price"],
                "line_total": line_total,
            }
        )
    total = sum(linea["line_total"] for linea in lineas)

    try:
        sale, sale_items = _guardar_venta(session, user["id"], lineas, total)
    except Exception as exc:
        # 4) Inventario ya descontó: se compensa antes de responder 502.
        session.rollback()
        _compensar(client, lineas, reference, token)
        raise HTTPException(
            status_code=502, detail="Error al registrar la venta"
        ) from exc

    return SaleCreatedOut(
        venta=SaleOut(
            id=sale.id,
            employee_id=sale.employee_id,
            total=sale.total,
            created_at=sale.created_at,
            items=[
                SaleItemOut(
                    id=item.id,
                    product_id=item.product_id,
                    product_name=item.product_name,
                    category=item.category,
                    quantity=item.quantity,
                    unit_price=item.unit_price,
                    line_total=item.line_total,
                )
                for item in sale_items
            ],
        ),
        stock=[
            SaleStockOut(product_id=entry["product_id"], stock=entry["stock"])
            for entry in salida
        ],
    )
