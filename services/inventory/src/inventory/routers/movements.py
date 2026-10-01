from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from inventory.deps import get_session, parse_date_bound
from inventory.models import Product, StockMovement
from inventory.rbac import get_current_user, require_roles
from inventory.schemas import (
    MovementCreate,
    MovementCreateOut,
    MovementOut,
    MovementPage,
)

router = APIRouter(tags=["movements"])


def _iso(value: datetime) -> str:
    """Normaliza a ISO-8601 naive con segundos, igual que seed.py."""
    return value.replace(tzinfo=None).isoformat(timespec="seconds")


def _to_out(movement: StockMovement) -> MovementOut:
    return MovementOut(
        id=movement.id,
        product_id=movement.product_id,
        movement_type=movement.movement_type,
        quantity=movement.quantity,
        reason=movement.reason,
        reference=movement.reference,
        created_at=movement.created_at,
    )


@router.get("/movements", response_model=MovementPage)
def list_movements(
    product_id: int | None = None,
    movement_type: str | None = None,
    reason: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    user: dict = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> MovementPage:
    query = session.query(StockMovement)
    if product_id is not None:
        query = query.filter(StockMovement.product_id == product_id)
    if movement_type is not None:
        query = query.filter(StockMovement.movement_type == movement_type)
    if reason is not None:
        query = query.filter(StockMovement.reason == reason)
    date_from_bound = parse_date_bound(date_from, end=False)
    date_to_bound = parse_date_bound(date_to, end=True)
    if date_from_bound is not None:
        query = query.filter(StockMovement.created_at >= date_from_bound)
    if date_to_bound is not None:
        query = query.filter(StockMovement.created_at <= date_to_bound)
    query = query.order_by(
        StockMovement.created_at.desc(), StockMovement.id.desc()
    )

    total = query.count()
    movements = query.offset((page - 1) * page_size).limit(page_size).all()
    return MovementPage(
        items=[_to_out(movement) for movement in movements],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.post("/movements", response_model=MovementCreateOut, status_code=201)
def create_movement(
    payload: MovementCreate,
    user: dict = Depends(require_roles("empleado", "admin")),
    session: Session = Depends(get_session),
) -> MovementCreateOut:
    product = session.get(Product, payload.product_id)
    if product is None:
        raise HTTPException(status_code=404, detail="Producto no encontrado")

    delta = payload.quantity if payload.movement_type == "entrada" else -payload.quantity
    resulting_stock = product.stock + delta
    if resulting_stock < 0:
        # Sin cambios: no se toca el stock ni se crea el movimiento.
        raise HTTPException(status_code=409, detail="Stock insuficiente")

    product.stock = resulting_stock
    movement = StockMovement(
        product_id=product.id,
        movement_type=payload.movement_type,
        quantity=payload.quantity,
        reason=payload.reason,
        reference=payload.reference,
        created_at=_iso(datetime.now()),
    )
    session.add(movement)
    session.commit()
    session.refresh(movement)
    return MovementCreateOut(movement=_to_out(movement), stock=product.stock)
