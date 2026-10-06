# main.py
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path  # use to locate the .env file

import jwt
import pyodbc
from argon2 import PasswordHasher
from argon2.exceptions import VerificationError, VerifyMismatchError
from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordBearer
from pydantic import BaseModel, Field

load_dotenv(Path(__file__).with_name(".env"))

JWT_SECRET = os.getenv("JWT_SECRET_KEY", "")
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
TOKEN_MINUTES = int(os.getenv("ACCESS_TOKEN_MINUTES", "30"))
DB_SERVER = os.getenv("DB_SERVER", r"AbdulMoiz\sqlserver16")
DB_NAME = os.getenv("DB_NAME", "GBMS")
DB_DRIVER = os.getenv("DB_DRIVER", "ODBC Driver 18 for SQL Server")
DB_USER = os.getenv("DB_USER", "")
DB_PASSWORD = os.getenv("DB_PASSWORD", "")

if not JWT_SECRET or JWT_SECRET == "replace-with-a-long-random-secret":
    raise RuntimeError(
        "Set JWT_SECRET_KEY to a private random value in FastAPI (BackEnd)/.env"
    )

password_hasher = PasswordHasher()
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")
app = FastAPI(title="GBMS API", version="1.0.0")
allowed_origins = [
    origin.strip()
    for origin in os.getenv(
        "CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173"
    ).split(",")
    if origin.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["Authorization", "Content-Type"],
)


def get_connection():
    if DB_USER and DB_PASSWORD:
        auth = f"UID={DB_USER};PWD={DB_PASSWORD};"
    else:
        auth = "Trusted_Connection=yes;"
    connection_string = f"DRIVER={{{DB_DRIVER}}};SERVER={DB_SERVER};DATABASE={DB_NAME};{auth}TrustServerCertificate=yes;"
    try:
        return pyodbc.connect(connection_string, timeout=5)
    except pyodbc.Error as exc:
        raise HTTPException(
            status_code=503,
            detail="Database is unavailable. Check the GBMS database connection settings.",
        ) from exc
    

def public_user(row):
    return {
        "user_id": row[0],
        "username": row[1],
        "full_name": row[2],
        "email": row[3],
        "role_name": row[4],
    }


class LoginPayload(BaseModel):
    username: str = Field(min_length=1, max_length=80)
    password: str = Field(min_length=1, max_length=1024)


def make_token(user):
    now = datetime.now(timezone.utc)
    return jwt.encode(
        {
            "sub": str(user["user_id"]),
            "iat": now,
            "exp": now + timedelta(minutes=TOKEN_MINUTES),
            "type": "access",
        },
        JWT_SECRET,
        algorithm=JWT_ALGORITHM,
    )


def get_current_user(token: str = Depends(oauth2_scheme)):
    unauthorized = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Your session is invalid or has expired.",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        claims = jwt.decode(
            token,
            JWT_SECRET,
            algorithms=[JWT_ALGORITHM],
            options={"require": ["sub", "iat", "exp", "type"]},
        )
        if claims.get("type") != "access":
            raise unauthorized
        user_id = int(claims["sub"])
    except (jwt.PyJWTError, ValueError, TypeError) as exc:
        raise unauthorized from exc
    with get_connection() as connection:
        row = (
            connection.cursor()
            .execute(
                """SELECT u.UserID, u.Username, u.FullName, u.Email, r.RoleName, u.AccountStatus
            FROM dbo.Users u JOIN dbo.Roles r ON r.RoleID=u.RoleID WHERE u.UserID=?""",
                user_id,
            )
            .fetchone()
        )
    if not row:
        raise unauthorized
    if row[5] != "ACTIVE":
        raise HTTPException(
            status_code=403,
            detail="This account is not active. Contact your administrator.",
        )
    return public_user(row)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/api/v1/auth/login")
def login(payload: LoginPayload):
    with get_connection() as connection:
        row = (
            connection.cursor()
            .execute(
                """SELECT u.UserID, u.Username, u.FullName, u.Email, r.RoleName,
            u.AccountStatus, u.PasswordHash FROM dbo.Users u JOIN dbo.Roles r ON r.RoleID=u.RoleID
            WHERE u.Username=?""",
                payload.username.strip(),
            )
            .fetchone()
        )
    if not row:
        raise HTTPException(status_code=401, detail="Invalid username or password.")
    try:
        password_hasher.verify(row[6], payload.password)
    except (VerifyMismatchError, VerificationError, ValueError):
        raise HTTPException(status_code=401, detail="Invalid username or password.")
    if row[5] != "ACTIVE":
        raise HTTPException(
            status_code=403,
            detail="This account is not active. Contact your administrator.",
        )
    user = public_user(row)
    return {
        "access_token": make_token(user),
        "token_type": "bearer",
        "expires_in": TOKEN_MINUTES * 60,
        "user": user,
    }


@app.get("/api/v1/auth/me")
def me(user=Depends(get_current_user)):
    return user


@app.get("/api/v1/dashboard")
def dashboard(user=Depends(get_current_user)):
    return {
        "message": "You have authenticated access to the GBMS workspace.",
        "user": user,
    }
