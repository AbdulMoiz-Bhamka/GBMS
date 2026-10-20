# app/core/config.py
"""Application settings loaded from the backend's local .env file."""

import os
from pathlib import Path

from dotenv import load_dotenv

BACKEND_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(BACKEND_ROOT / ".env")

JWT_SECRET = os.getenv("JWT_SECRET_KEY", "")
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
TOKEN_MINUTES = int(os.getenv("ACCESS_TOKEN_MINUTES", "30"))
DB_SERVER = os.getenv(
    "DB_SERVER", r"AbdulMoiz\sqlserver16" if os.name == "nt" else ""
).strip()
DB_PORT = os.getenv("DB_PORT", "").strip()
DB_NAME = os.getenv("DB_NAME", "GBMS")
DB_DRIVER = os.getenv("DB_DRIVER", "ODBC Driver 18 for SQL Server")
DB_USER = os.getenv("DB_USER", "")
DB_PASSWORD = os.getenv("DB_PASSWORD", "")

if not JWT_SECRET or JWT_SECRET == "replace-with-a-long-random-secret":
    raise RuntimeError(
        "Set JWT_SECRET_KEY to a private random value in FastAPI (BackEnd)/.env"
    )

configured_origins = {
    origin.strip().rstrip("/")
    for origin in os.getenv(
        "CORS_ORIGINS",
        "http://localhost:5173,http://127.0.0.1:5173,https://gbms786.vercel.app",
    ).split(",")
    if origin.strip()
}
ALLOWED_ORIGINS = sorted(
    configured_origins
    | {"http://localhost:5173", "http://127.0.0.1:5173", "https://gbms786.vercel.app"}
)

COMPANY_CODE_PATTERN = r"^[A-Za-z0-9][A-Za-z0-9_-]{1,29}$"
SUPPLIER_CODE_PATTERN = r"^[A-Za-z0-9][A-Za-z0-9_-]{1,39}$"
SKU_PATTERN = r"^[A-Za-z0-9][A-Za-z0-9._/-]{0,59}$"
EMAIL_PATTERN = r"^[^\s@]+@[^\s@]+\.[^\s@]+$"
