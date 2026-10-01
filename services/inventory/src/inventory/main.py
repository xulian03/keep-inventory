from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from inventory.config import FRONTEND_URL, SERVICE_NAME
from inventory.routers.catalog import router as catalog_router
from inventory.routers.internal import router as internal_router
from inventory.routers.movements import router as movements_router
from inventory.routers.purchase_orders import router as purchase_orders_router

app = FastAPI(title=f"KeepInventory {SERVICE_NAME}")

app.include_router(catalog_router)
app.include_router(internal_router)
app.include_router(movements_router)
app.include_router(purchase_orders_router)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[FRONTEND_URL],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict:
    return {"service": SERVICE_NAME, "status": "ok"}
