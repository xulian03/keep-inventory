import os

from dotenv import load_dotenv

load_dotenv()

SERVICE_NAME = "sales"
PORT = int(os.getenv("SALES_PORT", "8003"))
JWT_SECRET = os.getenv("JWT_SECRET", "dev-secret-keep-inventory")
JWT_EXPIRES_HOURS = 24
INVENTORY_URL = os.getenv("INVENTORY_URL", "http://localhost:8002")
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:5173")
