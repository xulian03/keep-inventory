import os

from dotenv import load_dotenv

load_dotenv()

SERVICE_NAME = "inventory"
PORT = int(os.getenv("INVENTORY_PORT", "8002"))
JWT_SECRET = os.getenv("JWT_SECRET", "dev-secret-keep-inventory")
JWT_EXPIRES_HOURS = 24
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:5173")
