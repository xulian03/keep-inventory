from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import or_
from sqlalchemy.orm import Session

from inventory.deps import get_session
from inventory.models import Product, Supplier
from inventory.rbac import get_current_user, require_roles
from inventory.schemas import (
    CategoriesOut,
    ProductDetail,
    ProductOut,
    ProductPage,
    ProductUpdate,
    SupplierOut,
    ThresholdUpdate,
)
from inventory.state import AGOTADO, BAJO, compute_state

router = APIRouter(tags=["catalog"])


def _to_out(product: Product) -> ProductOut:
    return ProductOut(
        id=product.id,
        name=product.name,
        brand=product.brand,
        category=product.category,
        subcategory=product.subcategory,
        type=product.type,
        sale_price=product.sale_price,
        market_price=product.market_price,
        rating=product.rating,
        is_active=bool(product.is_active),
        stock=product.stock,
        min_threshold=product.min_threshold,
        excess_threshold=product.excess_threshold,
        supplier_id=product.supplier_id,
        created_at=product.created_at,
        state=compute_state(
            product.stock, product.min_threshold, product.excess_threshold
        ),
    )


def _parse_ids(ids: str | None) -> list[int] | None:
    if ids is None:
        return None
    try:
        return [int(part) for part in ids.split(",") if part.strip()]
    except ValueError:
        raise HTTPException(status_code=422, detail="Parámetro ids inválido")


@router.get("/products", response_model=ProductPage)
def list_products(
    search: str | None = None,
    ids: str | None = None,
    category: str | None = None,
    subcategory: str | None = None,
    brand: str | None = None,
    supplier_id: int | None = None,
    state: str | None = None,
    is_active: bool | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    user: dict = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> ProductPage:
    id_list = _parse_ids(ids)

    query = session.query(Product)
    if id_list is not None:
        query = query.filter(Product.id.in_(id_list))
    if search:
        pattern = f"%{search}%"
        query = query.filter(
            or_(Product.name.ilike(pattern), Product.brand.ilike(pattern))
        )
    if category is not None:
        query = query.filter(Product.category == category)
    if subcategory is not None:
        query = query.filter(Product.subcategory == subcategory)
    if brand is not None:
        query = query.filter(Product.brand == brand)
    if supplier_id is not None:
        query = query.filter(Product.supplier_id == supplier_id)
    if is_active is not None:
        query = query.filter(Product.is_active == (1 if is_active else 0))
    query = query.order_by(Product.id.asc())

    # ids= ignora la paginación: devuelve todas las coincidencias.
    if id_list is not None:
        items = [_to_out(product) for product in query.all()]
        if state is not None:
            items = [item for item in items if item.state == state]
        total = len(items)
        return ProductPage(items=items, total=total, page=1, page_size=total)

    # El state se calcula por ítem; cuando se filtra por él hay que aplicarlo
    # en Python para poder contar el total correcto.
    if state is not None:
        matched = [_to_out(product) for product in query.all()]
        matched = [item for item in matched if item.state == state]
        total = len(matched)
        start = (page - 1) * page_size
        return ProductPage(
            items=matched[start : start + page_size],
            total=total,
            page=page,
            page_size=page_size,
        )

    total = query.count()
    products = query.offset((page - 1) * page_size).limit(page_size).all()
    return ProductPage(
        items=[_to_out(product) for product in products],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/products/{product_id}", response_model=ProductDetail)
def get_product(
    product_id: int,
    user: dict = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> ProductDetail:
    product = session.get(Product, product_id)
    if product is None:
        raise HTTPException(status_code=404, detail="Producto no encontrado")
    supplier_name = None
    if product.supplier_id is not None:
        supplier = session.get(Supplier, product.supplier_id)
        supplier_name = supplier.name if supplier is not None else None
    base = _to_out(product)
    return ProductDetail(**base.model_dump(), supplier_name=supplier_name)


@router.patch("/products/{product_id}", response_model=ProductOut)
def update_product(
    product_id: int,
    payload: ProductUpdate,
    user: dict = Depends(require_roles("admin")),
    session: Session = Depends(get_session),
) -> ProductOut:
    product = session.get(Product, product_id)
    if product is None:
        raise HTTPException(status_code=404, detail="Producto no encontrado")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(product, field, value)
    session.commit()
    session.refresh(product)
    return _to_out(product)


@router.patch("/products/{product_id}/threshold", response_model=ProductOut)
def update_threshold(
    product_id: int,
    payload: ThresholdUpdate,
    user: dict = Depends(require_roles("admin")),
    session: Session = Depends(get_session),
) -> ProductOut:
    product = session.get(Product, product_id)
    if product is None:
        raise HTTPException(status_code=404, detail="Producto no encontrado")
    updates = payload.model_dump(exclude_unset=True)
    min_threshold = updates.get("min_threshold", product.min_threshold)
    excess_threshold = updates.get("excess_threshold", product.excess_threshold)
    if excess_threshold < min_threshold:
        raise HTTPException(
            status_code=422,
            detail="excess_threshold debe ser mayor o igual que min_threshold",
        )
    product.min_threshold = min_threshold
    product.excess_threshold = excess_threshold
    session.commit()
    session.refresh(product)
    return _to_out(product)


@router.get("/suppliers", response_model=list[SupplierOut])
def list_suppliers(
    user: dict = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> list[SupplierOut]:
    suppliers = session.query(Supplier).order_by(Supplier.id.asc()).all()
    return [
        SupplierOut(
            id=supplier.id,
            name=supplier.name,
            contact_email=supplier.contact_email,
            lead_time_days=supplier.lead_time_days,
        )
        for supplier in suppliers
    ]


@router.get("/alerts", response_model=ProductPage)
def list_alerts(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    user: dict = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> ProductPage:
    # El state no se almacena: se filtra en Python y se ordena por stock asc.
    products = session.query(Product).order_by(
        Product.stock.asc(), Product.id.asc()
    ).all()
    alerts = [
        _to_out(product)
        for product in products
        if compute_state(
            product.stock, product.min_threshold, product.excess_threshold
        )
        in (AGOTADO, BAJO)
    ]
    total = len(alerts)
    start = (page - 1) * page_size
    return ProductPage(
        items=alerts[start : start + page_size],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/categories", response_model=CategoriesOut)
def list_categories(
    user: dict = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> CategoriesOut:
    categories = [
        row[0]
        for row in session.query(Product.category)
        .distinct()
        .order_by(Product.category)
        .all()
    ]
    subcategories = [
        row[0]
        for row in session.query(Product.subcategory)
        .distinct()
        .order_by(Product.subcategory)
        .all()
    ]
    return CategoriesOut(categories=categories, subcategories=subcategories)
