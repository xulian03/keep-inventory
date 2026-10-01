from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from inventory.deps import get_session, parse_date_bound
from inventory.models import (
    Product,
    PurchaseOrder,
    PurchaseOrderItem,
    Supplier,
)
from inventory.rbac import get_current_user, require_roles
from inventory.schemas import (
    PurchaseOrderCreate,
    PurchaseOrderDetail,
    PurchaseOrderItemOut,
    PurchaseOrderOut,
    PurchaseOrderPage,
    PurchaseOrderUpdate,
)

router = APIRouter(tags=["purchase-orders"])


def _now_iso() -> str:
    """ISO-8601 naive con segundos, igual que seed.py y movements.py."""
    return datetime.now().replace(tzinfo=None).isoformat(timespec="seconds")


def _item_out(item: PurchaseOrderItem) -> PurchaseOrderItemOut:
    return PurchaseOrderItemOut(
        id=item.id,
        product_id=item.product_id,
        quantity=item.quantity,
        unit_cost=item.unit_cost,
        total=item.quantity * item.unit_cost,
    )


def _items_of(session: Session, order_id: int) -> list[PurchaseOrderItem]:
    return (
        session.query(PurchaseOrderItem)
        .filter(PurchaseOrderItem.order_id == order_id)
        .order_by(PurchaseOrderItem.id.asc())
        .all()
    )


def _totals_by_order(
    session: Session, order_ids: list[int]
) -> dict[int, tuple[float, int]]:
    if not order_ids:
        return {}
    rows = (
        session.query(
            PurchaseOrderItem.order_id,
            func.coalesce(
                func.sum(PurchaseOrderItem.quantity * PurchaseOrderItem.unit_cost),
                0.0,
            ),
            func.count(PurchaseOrderItem.id),
        )
        .filter(PurchaseOrderItem.order_id.in_(order_ids))
        .group_by(PurchaseOrderItem.order_id)
        .all()
    )
    return {row[0]: (float(row[1]), int(row[2])) for row in rows}


def _order_out(
    order: PurchaseOrder, totals: dict[int, tuple[float, int]]
) -> PurchaseOrderOut:
    total, item_count = totals.get(order.id, (0.0, 0))
    return PurchaseOrderOut(
        id=order.id,
        supplier_id=order.supplier_id,
        status=order.status,
        expected_date=order.expected_date,
        created_at=order.created_at,
        received_at=order.received_at,
        total=total,
        item_count=item_count,
    )


def _detail_out(session: Session, order: PurchaseOrder) -> PurchaseOrderDetail:
    items = [_item_out(item) for item in _items_of(session, order.id)]
    total = sum(item.total for item in items)
    return PurchaseOrderDetail(
        **_order_out(order, {order.id: (total, len(items))}).model_dump(),
        items=items,
    )


def _validar_referencias(
    session: Session, supplier_id: int, product_ids: list[int]
) -> Supplier:
    supplier = session.get(Supplier, supplier_id)
    if supplier is None:
        raise HTTPException(status_code=422, detail="Proveedor no encontrado")
    found = {
        row[0]
        for row in session.query(Product.id).filter(Product.id.in_(product_ids)).all()
    }
    missing = set(product_ids) - found
    if missing:
        raise HTTPException(status_code=422, detail="Producto no encontrado")
    return supplier


def _get_order_or_404(session: Session, order_id: int) -> PurchaseOrder:
    order = session.get(PurchaseOrder, order_id)
    if order is None:
        raise HTTPException(status_code=404, detail="Orden no encontrada")
    return order


@router.post("/purchase-orders", response_model=PurchaseOrderDetail, status_code=201)
def create_purchase_order(
    payload: PurchaseOrderCreate,
    user: dict = Depends(require_roles("admin")),
    session: Session = Depends(get_session),
) -> PurchaseOrderDetail:
    product_ids = [item.product_id for item in payload.items]
    supplier = _validar_referencias(session, payload.supplier_id, product_ids)

    if payload.expected_date is not None:
        expected_date = payload.expected_date.replace(tzinfo=None).isoformat(
            timespec="seconds"
        )
    else:
        # La columna expected_date es NOT NULL: sin fecha explícita se estima
        # la entrega usando el lead time del proveedor.
        expected_date = (
            datetime.now() + timedelta(days=supplier.lead_time_days)
        ).replace(tzinfo=None).isoformat(timespec="seconds")

    order = PurchaseOrder(
        supplier_id=payload.supplier_id,
        status="borrador",
        expected_date=expected_date,
        created_at=_now_iso(),
        received_at=None,
    )
    session.add(order)
    session.flush()
    for item in payload.items:
        session.add(
            PurchaseOrderItem(
                order_id=order.id,
                product_id=item.product_id,
                quantity=item.quantity,
                unit_cost=item.unit_cost,
            )
        )
    session.commit()
    session.refresh(order)
    return _detail_out(session, order)


@router.get("/purchase-orders", response_model=PurchaseOrderPage)
def list_purchase_orders(
    status: str | None = None,
    supplier_id: int | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    user: dict = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> PurchaseOrderPage:
    query = session.query(PurchaseOrder)
    if status is not None:
        query = query.filter(PurchaseOrder.status == status)
    if supplier_id is not None:
        query = query.filter(PurchaseOrder.supplier_id == supplier_id)

    date_from_bound = parse_date_bound(date_from, end=False)
    date_to_bound = parse_date_bound(date_to, end=True)
    if date_from_bound is not None:
        query = query.filter(PurchaseOrder.created_at >= date_from_bound)
    if date_to_bound is not None:
        query = query.filter(PurchaseOrder.created_at <= date_to_bound)

    query = query.order_by(
        PurchaseOrder.created_at.desc(), PurchaseOrder.id.desc()
    )

    total = query.count()
    orders = query.offset((page - 1) * page_size).limit(page_size).all()
    totals = _totals_by_order(session, [order.id for order in orders])
    return PurchaseOrderPage(
        items=[_order_out(order, totals) for order in orders],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/purchase-orders/{order_id}", response_model=PurchaseOrderDetail)
def get_purchase_order(
    order_id: int,
    user: dict = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> PurchaseOrderDetail:
    order = _get_order_or_404(session, order_id)
    return _detail_out(session, order)


@router.patch("/purchase-orders/{order_id}", response_model=PurchaseOrderDetail)
def update_purchase_order(
    order_id: int,
    payload: PurchaseOrderUpdate,
    user: dict = Depends(require_roles("admin")),
    session: Session = Depends(get_session),
) -> PurchaseOrderDetail:
    order = _get_order_or_404(session, order_id)
    if order.status != "borrador":
        raise HTTPException(
            status_code=409, detail="Solo se puede editar una orden en borrador"
        )

    if payload.expected_date is not None:
        order.expected_date = payload.expected_date.replace(
            tzinfo=None
        ).isoformat(timespec="seconds")

    if payload.items is not None:
        product_ids = [item.product_id for item in payload.items]
        _validar_referencias(session, order.supplier_id, product_ids)
        session.query(PurchaseOrderItem).filter(
            PurchaseOrderItem.order_id == order.id
        ).delete()
        for item in payload.items:
            session.add(
                PurchaseOrderItem(
                    order_id=order.id,
                    product_id=item.product_id,
                    quantity=item.quantity,
                    unit_cost=item.unit_cost,
                )
            )

    session.commit()
    session.refresh(order)
    return _detail_out(session, order)


@router.delete("/purchase-orders/{order_id}", status_code=204)
def delete_purchase_order(
    order_id: int,
    user: dict = Depends(require_roles("admin")),
    session: Session = Depends(get_session),
) -> None:
    order = _get_order_or_404(session, order_id)
    if order.status != "borrador":
        raise HTTPException(
            status_code=409, detail="Solo se puede eliminar una orden en borrador"
        )
    session.query(PurchaseOrderItem).filter(
        PurchaseOrderItem.order_id == order.id
    ).delete()
    session.delete(order)
    session.commit()
