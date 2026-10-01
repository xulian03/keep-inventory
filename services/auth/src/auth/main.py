from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from auth.config import FRONTEND_URL, SERVICE_NAME
from auth.routers.auth import router as auth_router

app = FastAPI(title=f"KeepInventory {SERVICE_NAME}")

app.include_router(auth_router)

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
