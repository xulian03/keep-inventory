from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from inventory.deps import get_session
from inventory.models import Product, StockMovement
from inventory.rbac import get_current_user
from inventory.schemas import (
    InternalSalidaCreate,
    InternalSalidaItemOut,
    InternalSalidaOut,
)

router = APIRouter(tags=["internal"])


def _now_iso() -> str:
    """ISO-8601 naive con segundos, igual que seed.py y movements.py."""
    return datetime.now().replace(tzinfo=None).isoformat(timespec="seconds")


@router.post("/internal/movements/salida", response_model=InternalSalidaOut)
def descontar_salida(
    payload: InternalSalidaCreate,
    user: dict = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> InternalSalidaOut:
    """Descuenta stock por una venta: UNA transacción, todo o nada.

    Valida el stock de todos los ítems antes de aplicar ningún cambio; si
    alguno no existe o no alcanza responde 409 sin descontar nada.
    """
    product_ids = [item.product_id for item in payload.items]
    products = {
        product.id: product
        for product in session.query(Product)
        .filter(Product.id.in_(product_ids))
        .all()
    }

    # Validación previa: nada se modifica hasta que todo el lote sea válido.
    for item in payload.items:
        product = products.get(item.product_id)
        if product is None:
            raise HTTPException(status_code=409, detail="Producto no encontrado")
        if product.stock < item.quantity:
            raise HTTPException(status_code=409, detail="Stock insuficiente")

    created_at = _now_iso()
    for item in payload.items:
        product = products[item.product_id]
        product.stock -= item.quantity
        session.add(
            StockMovement(
                product_id=item.product_id,
                movement_type="salida",
                quantity=item.quantity,
                reason="venta",
                reference=payload.reference,
                created_at=created_at,
            )
        )
    session.commit()

    return InternalSalidaOut(
        items=[
            InternalSalidaItemOut(
                product_id=item.product_id,
                stock=products[item.product_id].stock,
            )
            for item in payload.items
        ]
    )
