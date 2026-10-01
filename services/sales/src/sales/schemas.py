from pydantic import BaseModel, Field, model_validator


class SaleItemIn(BaseModel):
    product_id: int
    quantity: int = Field(gt=0)


class SaleCreate(BaseModel):
    """Alta de venta (POST /sales): ítems sin duplicados (ARCH §5.3)."""

    items: list[SaleItemIn]

    @model_validator(mode="after")
    def _validar(self) -> "SaleCreate":
        if not self.items:
            raise ValueError("items no puede estar vacío")
        product_ids = [item.product_id for item in self.items]
        if len(product_ids) != len(set(product_ids)):
            raise ValueError("items no puede tener product_id duplicados")
        return self


class SaleItemOut(BaseModel):
    id: int
    product_id: int
    product_name: str
    category: str
    quantity: int
    unit_price: float
    line_total: float


class SaleOut(BaseModel):
    id: int
    employee_id: int
    total: float
    created_at: str
    items: list[SaleItemOut]


class SalePage(BaseModel):
    items: list[SaleOut]
    total: int
    page: int
    page_size: int


class SaleStockOut(BaseModel):
    product_id: int
    stock: int


class SaleCreatedOut(BaseModel):
    """Respuesta 201 de POST /sales: venta + stock resultante por ítem."""

    venta: SaleOut
    stock: list[SaleStockOut]
