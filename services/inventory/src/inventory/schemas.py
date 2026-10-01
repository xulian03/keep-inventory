from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, model_validator


class ProductOut(BaseModel):
    id: int
    name: str
    brand: str
    category: str
    subcategory: str
    type: str
    sale_price: float
    market_price: float
    rating: float | None
    is_active: bool
    stock: int
    min_threshold: int
    excess_threshold: int
    supplier_id: int | None
    created_at: str
    state: str


class ProductDetail(ProductOut):
    supplier_name: str | None


class ProductPage(BaseModel):
    items: list[ProductOut]
    total: int
    page: int
    page_size: int


class CategoriesOut(BaseModel):
    categories: list[str]
    subcategories: list[str]


class SupplierOut(BaseModel):
    id: int
    name: str
    contact_email: str
    lead_time_days: int


class ProductUpdate(BaseModel):
    """Edición parcial (PATCH): solo se aplican los campos enviados."""

    name: str | None = Field(default=None, min_length=1)
    sale_price: float | None = Field(default=None, gt=0)
    market_price: float | None = Field(default=None, ge=0)
    is_active: bool | None = None

    @model_validator(mode="after")
    def _validar_campos(self) -> "ProductUpdate":
        for field in self.model_fields_set:
            if getattr(self, field) is None:
                raise ValueError(f"{field} no puede ser nulo")
        if "name" in self.model_fields_set and not (self.name or "").strip():
            raise ValueError("name no puede estar vacío")
        return self


class ThresholdUpdate(BaseModel):
    """Ajuste parcial de umbrales; la consistencia se valida en el endpoint."""

    min_threshold: int | None = Field(default=None, ge=0)
    excess_threshold: int | None = None

    @model_validator(mode="after")
    def _validar_campos(self) -> "ThresholdUpdate":
        for field in self.model_fields_set:
            if getattr(self, field) is None:
                raise ValueError(f"{field} no puede ser nulo")
        return self


class MovementOut(BaseModel):
    id: int
    product_id: int
    movement_type: str
    quantity: int
    reason: str
    reference: str | None
    created_at: str


class MovementPage(BaseModel):
    items: list[MovementOut]
    total: int
    page: int
    page_size: int


class MovementCreate(BaseModel):
    """Movimiento manual (POST /movements).

    reason sólo admite compra/ajuste: "venta" está reservado al endpoint interno
    de descuento por venta (ARCH §5.2).
    """

    product_id: int
    movement_type: Literal["entrada", "salida"]
    quantity: int = Field(gt=0)
    reason: Literal["compra", "ajuste"]
    reference: str | None = None


class MovementCreateOut(BaseModel):
    movement: MovementOut
    stock: int


class PurchaseOrderItemIn(BaseModel):
    product_id: int
    quantity: int = Field(gt=0)
    unit_cost: float = Field(ge=0)


def _validar_items(items: list[PurchaseOrderItemIn]) -> None:
    if not items:
        raise ValueError("items no puede estar vacío")
    product_ids = [item.product_id for item in items]
    if len(product_ids) != len(set(product_ids)):
        raise ValueError("items no puede tener product_id duplicados")


class PurchaseOrderCreate(BaseModel):
    supplier_id: int
    expected_date: datetime | None = None
    items: list[PurchaseOrderItemIn]

    @model_validator(mode="after")
    def _validar(self) -> "PurchaseOrderCreate":
        _validar_items(self.items)
        return self


class PurchaseOrderUpdate(BaseModel):
    """Edición de una orden borrador: reemplaza items y/o expected_date."""

    expected_date: datetime | None = None
    items: list[PurchaseOrderItemIn] | None = None

    @model_validator(mode="after")
    def _validar(self) -> "PurchaseOrderUpdate":
        if self.items is not None:
            _validar_items(self.items)
        return self


class PurchaseOrderItemOut(BaseModel):
    id: int
    product_id: int
    quantity: int
    unit_cost: float
    total: float


class PurchaseOrderOut(BaseModel):
    id: int
    supplier_id: int
    status: str
    expected_date: str
    created_at: str
    received_at: str | None
    total: float
    item_count: int


class PurchaseOrderDetail(PurchaseOrderOut):
    items: list[PurchaseOrderItemOut]


class PurchaseOrderPage(BaseModel):
    items: list[PurchaseOrderOut]
    total: int
    page: int
    page_size: int
