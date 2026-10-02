import os

from dotenv import load_dotenv

load_dotenv()

SERVICE_NAME = "sales"
DB_PATH = os.getenv("SALES_DB", "sales.db")
PORT = int(os.getenv("SALES_PORT", "8003"))
JWT_SECRET = os.getenv("JWT_SECRET", "dev-secret-keep-inventory")
JWT_EXPIRES_HOURS = 24
# 127.0.0.1 evita la resolución lenta de "localhost" en Windows.
INVENTORY_URL = os.getenv("INVENTORY_URL", "http://127.0.0.1:8002")
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:5173")
