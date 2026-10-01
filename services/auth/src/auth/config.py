import os

from dotenv import load_dotenv

load_dotenv()

SERVICE_NAME = "auth"
DB_PATH = os.getenv("AUTH_DB", "auth.db")
PORT = int(os.getenv("AUTH_PORT", "8001"))
JWT_SECRET = os.getenv("JWT_SECRET", "dev-secret-keep-inventory")
JWT_EXPIRES_HOURS = 24
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:5173")
