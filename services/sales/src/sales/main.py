from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from sales.config import FRONTEND_URL, SERVICE_NAME
from sales.routers.analytics import router as analytics_router
from sales.routers.predictions import router as predictions_router
from sales.routers.sales import router as sales_router

app = FastAPI(title=f"KeepInventory {SERVICE_NAME}")

app.include_router(sales_router)
app.include_router(analytics_router)
app.include_router(predictions_router)

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
