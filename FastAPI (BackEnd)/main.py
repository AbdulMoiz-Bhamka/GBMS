# main.py
"""GBMS API: existing JWT authentication plus company and inventory APIs."""

import os
import re
import logging
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path as FilePath
from typing import Literal

import jwt
import pyodbc
from argon2 import PasswordHasher
from argon2.exceptions import VerificationError, VerifyMismatchError
from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException, Path, Query, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, ConfigDict, Field, field_validator

load_dotenv(FilePath(__file__).with_name(".env"))

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
bearer_scheme = HTTPBearer(auto_error=False, scheme_name="BearerAuth")
app = FastAPI(title="GBMS API", version="1.1.0")
logger = logging.getLogger("gbms")
configured_origins = {
    origin.strip().rstrip("/")
    for origin in os.getenv(
        "CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173"
    ).split(",")
    if origin.strip()
}
allowed_origins = sorted(
    configured_origins | {"http://localhost:5173", "http://127.0.0.1:5173"}
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH"],
    allow_headers=["Authorization", "Content-Type"],
)


def get_connection():
    """Open the configured SQL Server connection without exposing its details."""
    if DB_USER and DB_PASSWORD:
        auth = f"UID={DB_USER};PWD={DB_PASSWORD};"
    else:
        auth = "Trusted_Connection=yes;"
    connection_string = (
        f"DRIVER={{{DB_DRIVER}}};SERVER={DB_SERVER};DATABASE={DB_NAME};"
        f"{auth}TrustServerCertificate=yes;"
    )
    try:
        return pyodbc.connect(connection_string, timeout=5)
    except pyodbc.Error as exc:
        raise HTTPException(
            status_code=503,
            detail="Database is unavailable. Check the GBMS database connection settings.",
        ) from exc


@contextmanager
def database_connection():
    connection = get_connection()
    try:
        yield connection
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


@contextmanager
def database_cursor(connection):
    cursor = connection.cursor()
    try:
        yield cursor
    finally:
        cursor.close()


def public_user(
    user_id, username, full_name, email, role_name, company_id, company_status
):
    return {
        "user_id": user_id,
        "username": username,
        "full_name": full_name,
        "email": email,
        "role_name": role_name,
        "company_id": company_id,
        "company_status": company_status,
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


def validate_role_company(role_name, company_id, company_status):
    """Use current database state, never a client-supplied tenant or role."""
    if role_name == "SUPER_ADMIN":
        if company_id is not None:
            raise HTTPException(
                status_code=403,
                detail="Platform administrator account configuration is invalid.",
            )
        return
    if company_id is None:
        raise HTTPException(
            status_code=403, detail="This account is not assigned to a company."
        )
    if company_status != "ACTIVE":
        raise HTTPException(status_code=403, detail="This company is inactive.")


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
):
    unauthorized = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Your session is invalid or has expired.",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise unauthorized
    token = credentials.credentials
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

    with database_connection() as connection, database_cursor(connection) as cursor:
        row = cursor.execute(
            """SELECT u.UserID, u.Username, u.FullName, u.Email, r.RoleName,
                      u.AccountStatus, u.CompanyID, c.CompanyStatus
               FROM dbo.Users AS u
               JOIN dbo.Roles AS r ON r.RoleID = u.RoleID
               LEFT JOIN dbo.Companies AS c ON c.CompanyID = u.CompanyID
               WHERE u.UserID = ?""",
            user_id,
        ).fetchone()

    if not row:
        raise unauthorized
    if row[5] != "ACTIVE":
        raise HTTPException(
            status_code=403,
            detail="This account is not active. Contact your administrator.",
        )
    validate_role_company(row[4], row[6], row[7])
    return public_user(*row[:5], row[6], row[7])


def require_super_admin(user=Depends(get_current_user)):
    if user["role_name"] != "SUPER_ADMIN":
        raise HTTPException(
            status_code=403, detail="Platform Super Admin access is required."
        )
    return user


def require_company_user(user=Depends(get_current_user)):
    inventory_roles = {"COMPANY_ADMIN", "SUB_ADMIN", "INVENTORY_USER"}
    if user["role_name"] not in inventory_roles or user["company_id"] is None:
        raise HTTPException(
            status_code=403, detail="An authorized company inventory role is required."
        )
    return user


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/api/v1/auth/login")
def login(payload: LoginPayload):
    with database_connection() as connection, database_cursor(connection) as cursor:
        row = cursor.execute(
            """SELECT u.UserID, u.Username, u.FullName, u.Email, r.RoleName,
                      u.AccountStatus, u.PasswordHash, u.CompanyID, c.CompanyStatus
               FROM dbo.Users AS u
               JOIN dbo.Roles AS r ON r.RoleID = u.RoleID
               LEFT JOIN dbo.Companies AS c ON c.CompanyID = u.CompanyID
               WHERE u.Username = ?""",
            payload.username.strip(),
        ).fetchone()
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
    validate_role_company(row[4], row[7], row[8])
    user = public_user(*row[:5], row[7], row[8])
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


# Company schemas and helpers -------------------------------------------------

COMPANY_CODE_PATTERN = r"^[A-Za-z0-9][A-Za-z0-9_-]{1,29}$"
SKU_PATTERN = r"^[A-Za-z0-9][A-Za-z0-9._/-]{0,59}$"
EMAIL_PATTERN = r"^[^\s@]+@[^\s@]+\.[^\s@]+$"


def normalize_email(value):
    if value is None:
        return None
    value = value.strip()
    if not value:
        return None
    if len(value) > 254 or not re.fullmatch(EMAIL_PATTERN, value):
        raise ValueError("Enter a valid email address.")
    return value


def normalize_required_text(value, label):
    value = value.strip()
    if not value:
        raise ValueError(f"{label} cannot be blank.")
    return value


class CompanyCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    company_name: str = Field(min_length=1, max_length=160)
    company_code: str = Field(min_length=2, max_length=30, pattern=COMPANY_CODE_PATTERN)
    email: str | None = Field(default=None, max_length=254)
    phone: str | None = Field(default=None, max_length=40)
    address: str | None = Field(default=None, max_length=400)

    @field_validator("company_name")
    @classmethod
    def company_name_not_blank(cls, value):
        return normalize_required_text(value, "Company name")

    @field_validator("company_code")
    @classmethod
    def company_code_normalized(cls, value):
        return value.upper()

    @field_validator("email")
    @classmethod
    def company_email_valid(cls, value):
        return normalize_email(value)

    @field_validator("phone", "address")
    @classmethod
    def optional_text_trimmed(cls, value):
        if value is None:
            return None
        value = value.strip()
        return value or None


class CompanyUpdate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    company_name: str | None = Field(default=None, min_length=1, max_length=160)
    company_code: str | None = Field(
        default=None, min_length=2, max_length=30, pattern=COMPANY_CODE_PATTERN
    )
    email: str | None = Field(default=None, max_length=254)
    phone: str | None = Field(default=None, max_length=40)
    address: str | None = Field(default=None, max_length=400)

    @field_validator("company_name")
    @classmethod
    def company_name_not_blank(cls, value):
        return (
            normalize_required_text(value, "Company name")
            if value is not None
            else value
        )

    @field_validator("company_code")
    @classmethod
    def company_code_normalized(cls, value):
        return value.upper() if value is not None else value

    @field_validator("email")
    @classmethod
    def company_email_valid(cls, value):
        return normalize_email(value)

    @field_validator("phone", "address")
    @classmethod
    def optional_text_trimmed(cls, value):
        if value is None:
            return None
        value = value.strip()
        return value or None


class CompanyStatusUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    company_status: Literal["ACTIVE", "INACTIVE"]


class CompanyUserCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    username: str = Field(min_length=3, max_length=80, pattern=r"^[A-Za-z0-9_.-]+$")
    full_name: str = Field(min_length=1, max_length=160)
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=12, max_length=128)
    role_name: Literal["COMPANY_ADMIN", "SUB_ADMIN", "INVENTORY_USER"] = "COMPANY_ADMIN"

    @field_validator("full_name")
    @classmethod
    def full_name_not_blank(cls, value):
        return normalize_required_text(value, "Full name")

    @field_validator("email")
    @classmethod
    def email_valid(cls, value):
        result = normalize_email(value)
        if result is None:
            raise ValueError("Enter a valid email address.")
        return result


class CompanyCategoryCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    category_name: str = Field(min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=300)

    @field_validator("category_name")
    @classmethod
    def category_name_not_blank(cls, value):
        return normalize_required_text(value, "Category name")


class ProductCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    sku: str = Field(min_length=1, max_length=60, pattern=SKU_PATTERN)
    product_name: str = Field(min_length=1, max_length=180)
    product_type: Literal["RAW_MATERIAL", "FINISHED_GOOD"]
    unit_id: int = Field(gt=0)
    category_id: int | None = Field(default=None, gt=0)
    description: str | None = Field(default=None, max_length=1000)
    reorder_level: Decimal = Field(
        default=Decimal("0"), ge=0, max_digits=18, decimal_places=3
    )

    @field_validator("product_name")
    @classmethod
    def product_name_not_blank(cls, value):
        return normalize_required_text(value, "Product name")

    @field_validator("sku")
    @classmethod
    def sku_normalized(cls, value):
        return value.upper()


class ProductUpdate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    sku: str | None = Field(
        default=None, min_length=1, max_length=60, pattern=SKU_PATTERN
    )
    product_name: str | None = Field(default=None, min_length=1, max_length=180)
    product_type: Literal["RAW_MATERIAL", "FINISHED_GOOD"] | None = None
    unit_id: int | None = Field(default=None, gt=0)
    category_id: int | None = Field(default=None, gt=0)
    description: str | None = Field(default=None, max_length=1000)
    reorder_level: Decimal | None = Field(
        default=None, ge=0, max_digits=18, decimal_places=3
    )

    @field_validator("product_name")
    @classmethod
    def product_name_not_blank(cls, value):
        return (
            normalize_required_text(value, "Product name")
            if value is not None
            else value
        )

    @field_validator("sku")
    @classmethod
    def sku_normalized(cls, value):
        return value.upper() if value is not None else value


class ProductStatusUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    is_active: bool


def duplicate_or_server_error(exc, entity):
    message = str(exc)
    if "2601" in message or "2627" in message:
        raise HTTPException(
            status_code=409, detail=f"A {entity} with that name or code already exists."
        ) from exc
    raise HTTPException(
        status_code=500, detail=f"Could not save the {entity}. Please try again."
    ) from exc


def serialize_company(row):
    return {
        "company_id": row[0],
        "company_name": row[1],
        "company_code": row[2],
        "email": row[3],
        "phone": row[4],
        "address": row[5],
        "company_status": row[6],
        "created_at": row[7],
        "updated_at": row[8],
    }


COMPANY_COLUMNS = "CompanyID, CompanyName, CompanyCode, Email, Phone, Address, CompanyStatus, CreatedAt, UpdatedAt"


@app.get("/api/v1/companies")
def list_companies(
    search: str = Query(default="", max_length=120),
    limit: int = Query(default=25, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    _admin=Depends(require_super_admin),
):
    search = search.strip()
    where = (
        "WHERE CompanyName LIKE ? OR CompanyCode LIKE ? OR Email LIKE ?"
        if search
        else ""
    )
    search_params = [f"%{search}%"] * 3 if search else []
    with database_connection() as connection, database_cursor(connection) as cursor:
        total = cursor.execute(
            f"SELECT COUNT(*) FROM dbo.Companies {where}", *search_params
        ).fetchone()[0]
        rows = cursor.execute(
            f"SELECT {COMPANY_COLUMNS} FROM dbo.Companies {where} ORDER BY CompanyName, CompanyID OFFSET ? ROWS FETCH NEXT ? ROWS ONLY",
            *search_params,
            offset,
            limit,
        ).fetchall()
    return {
        "items": [serialize_company(row) for row in rows],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


@app.post("/api/v1/companies", status_code=status.HTTP_201_CREATED)
def create_company(payload: CompanyCreate, _admin=Depends(require_super_admin)):
    with database_connection() as connection, database_cursor(connection) as cursor:
        try:
            row = cursor.execute(
                """INSERT INTO dbo.Companies (CompanyName, CompanyCode, Email, Phone, Address)
                   OUTPUT INSERTED.CompanyID, INSERTED.CompanyName, INSERTED.CompanyCode,
                          INSERTED.Email, INSERTED.Phone, INSERTED.Address,
                          INSERTED.CompanyStatus, INSERTED.CreatedAt, INSERTED.UpdatedAt
                   VALUES (?, ?, ?, ?, ?)""",
                payload.company_name,
                payload.company_code,
                payload.email,
                payload.phone,
                payload.address,
            ).fetchone()
            connection.commit()
        except pyodbc.IntegrityError as exc:
            duplicate_or_server_error(exc, "company")
    return serialize_company(row)


@app.get("/api/v1/companies/{company_id}")
def get_company(company_id: int = Path(gt=0), _admin=Depends(require_super_admin)):
    with database_connection() as connection, database_cursor(connection) as cursor:
        row = cursor.execute(
            f"SELECT {COMPANY_COLUMNS} FROM dbo.Companies WHERE CompanyID = ?",
            company_id,
        ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Company not found.")
    return serialize_company(row)


@app.get("/api/v1/companies/{company_id}/users")
def list_company_users(
    company_id: int = Path(gt=0), _admin=Depends(require_super_admin)
):
    with database_connection() as connection, database_cursor(connection) as cursor:
        company = cursor.execute(
            "SELECT CompanyID FROM dbo.Companies WHERE CompanyID = ?", company_id
        ).fetchone()
        if not company:
            raise HTTPException(status_code=404, detail="Company not found.")
        rows = cursor.execute(
            """SELECT u.UserID, u.Username, u.FullName, u.Email, r.RoleName,
                      u.AccountStatus, u.CreatedAt
               FROM dbo.Users AS u JOIN dbo.Roles AS r ON r.RoleID = u.RoleID
               WHERE u.CompanyID = ? ORDER BY u.FullName, u.UserID""",
            company_id,
        ).fetchall()
    return {
        "items": [
            {
                "user_id": row[0],
                "username": row[1],
                "full_name": row[2],
                "email": row[3],
                "role_name": row[4],
                "account_status": row[5],
                "created_at": row[6],
            }
            for row in rows
        ]
    }


@app.post("/api/v1/companies/{company_id}/users", status_code=status.HTTP_201_CREATED)
def create_company_user(
    payload: CompanyUserCreate,
    company_id: int = Path(gt=0),
    _admin=Depends(require_super_admin),
):
    with database_connection() as connection, database_cursor(connection) as cursor:
        company = cursor.execute(
            "SELECT CompanyStatus FROM dbo.Companies WHERE CompanyID = ?", company_id
        ).fetchone()
        if not company:
            raise HTTPException(status_code=404, detail="Company not found.")
        if company[0] != "ACTIVE":
            raise HTTPException(
                status_code=409, detail="Activate the company before creating users."
            )
        role = cursor.execute(
            "SELECT RoleID FROM dbo.Roles WHERE RoleName = ?", payload.role_name
        ).fetchone()
        if not role:
            logger.error(
                "Configured company role is missing from dbo.Roles: %s",
                payload.role_name,
            )
            raise HTTPException(
                status_code=500,
                detail="The selected account role is not configured. Contact support.",
            )
        try:
            identity_row = cursor.execute(
                """SET NOCOUNT ON;
                   INSERT INTO dbo.Users (Username, FullName, Email, PasswordHash, RoleID, CompanyID)
                   VALUES (?, ?, ?, ?, ?, ?);
                   SELECT CONVERT(INT, SCOPE_IDENTITY());
                   SET NOCOUNT OFF;""",
                payload.username,
                payload.full_name,
                payload.email,
                password_hasher.hash(payload.password),
                role[0],
                company_id,
            ).fetchone()
            # Keep SCOPE_IDENTITY() in the same SQL batch as the INSERT so the
            # identity remains in scope. OUTPUT is not usable here because the
            # Users table has an enabled AFTER INSERT trigger.
            user_id = identity_row[0] if identity_row else None
            if user_id is None:
                raise RuntimeError("SQL Server did not return the inserted user ID.")
            row = cursor.execute(
                """SELECT UserID, Username, FullName, Email, AccountStatus, CreatedAt
                   FROM dbo.Users WHERE UserID = ?""",
                user_id,
            ).fetchone()
            if not row:
                raise RuntimeError("The inserted company user could not be read back.")
            connection.commit()
        except HTTPException:
            raise
        except pyodbc.IntegrityError as exc:
            message = str(exc)
            if "2601" in message or "2627" in message:
                if "UQ_Users_Username" in message:
                    detail = "That username is already in use. Choose another username."
                elif "UQ_Users_Email" in message:
                    detail = "That email address is already in use. Use another email address."
                else:
                    detail = "A user with that username or email already exists."
                raise HTTPException(status_code=409, detail=detail) from exc
            logger.exception(
                "Integrity failure while creating company user (company_id=%s, role=%s).",
                company_id,
                payload.role_name,
            )
            raise HTTPException(
                status_code=500,
                detail="Could not create the company account because of a database integrity error.",
            ) from exc
        except pyodbc.Error as exc:
            logger.exception(
                "SQL Server error while creating company user (company_id=%s, role=%s).",
                company_id,
                payload.role_name,
            )
            raise HTTPException(
                status_code=500,
                detail="Could not create the company account because of a database error. Check the server log.",
            ) from exc
        except Exception as exc:
            logger.exception(
                "Unexpected failure while creating company user (company_id=%s, role=%s).",
                company_id,
                payload.role_name,
            )
            raise HTTPException(
                status_code=500,
                detail="Could not create the company account. Check the server log.",
            ) from exc
    return {
        "user_id": row[0],
        "username": row[1],
        "full_name": row[2],
        "email": row[3],
        "role_name": payload.role_name,
        "account_status": row[4],
        "created_at": row[5],
    }


@app.put("/api/v1/companies/{company_id}")
def update_company(
    payload: CompanyUpdate,
    company_id: int = Path(gt=0),
    _admin=Depends(require_super_admin),
):
    values = payload.model_dump(exclude_unset=True)
    if not values:
        raise HTTPException(
            status_code=400, detail="Provide at least one company field to update."
        )
    if any(
        values.get(key) is None
        for key in ("company_name", "company_code")
        if key in values
    ):
        raise HTTPException(
            status_code=422, detail="Company name and code cannot be empty."
        )
    columns = {
        "company_name": "CompanyName",
        "company_code": "CompanyCode",
        "email": "Email",
        "phone": "Phone",
        "address": "Address",
    }
    assignments = [f"{columns[name]} = ?" for name in values]
    parameters = list(values.values())
    assignments.append("UpdatedAt = SYSUTCDATETIME()")
    parameters.append(company_id)
    with database_connection() as connection, database_cursor(connection) as cursor:
        try:
            row = cursor.execute(
                f"""UPDATE dbo.Companies SET {', '.join(assignments)}
                    OUTPUT INSERTED.CompanyID, INSERTED.CompanyName, INSERTED.CompanyCode,
                           INSERTED.Email, INSERTED.Phone, INSERTED.Address,
                           INSERTED.CompanyStatus, INSERTED.CreatedAt, INSERTED.UpdatedAt
                    WHERE CompanyID = ?""",
                *parameters,
            ).fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="Company not found.")
            connection.commit()
        except pyodbc.IntegrityError as exc:
            duplicate_or_server_error(exc, "company")
    return serialize_company(row)


@app.patch("/api/v1/companies/{company_id}/status")
def update_company_status(
    payload: CompanyStatusUpdate,
    company_id: int = Path(gt=0),
    _admin=Depends(require_super_admin),
):
    with database_connection() as connection, database_cursor(connection) as cursor:
        row = cursor.execute(
            f"""UPDATE dbo.Companies SET CompanyStatus = ?, UpdatedAt = SYSUTCDATETIME()
                OUTPUT INSERTED.CompanyID, INSERTED.CompanyName, INSERTED.CompanyCode,
                       INSERTED.Email, INSERTED.Phone, INSERTED.Address,
                       INSERTED.CompanyStatus, INSERTED.CreatedAt, INSERTED.UpdatedAt
                WHERE CompanyID = ?""",
            payload.company_status,
            company_id,
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Company not found.")
        connection.commit()
    return serialize_company(row)


# Company-scoped inventory APIs ---------------------------------------------


def ensure_category_for_company(cursor, category_id, company_id):
    if category_id is None:
        return
    exists = cursor.execute(
        "SELECT 1 FROM dbo.ProductCategories WHERE CategoryID = ? AND CompanyID = ?",
        category_id,
        company_id,
    ).fetchone()
    if not exists:
        raise HTTPException(
            status_code=422,
            detail="The selected category is not available to your company.",
        )


def ensure_unit_exists(cursor, unit_id):
    exists = cursor.execute(
        "SELECT 1 FROM dbo.UnitsOfMeasure WHERE UnitID = ? AND IsActive = 1", unit_id
    ).fetchone()
    if not exists:
        raise HTTPException(
            status_code=422, detail="Select a valid active unit of measure."
        )


def serialize_product(row):
    return {
        "product_id": row[0],
        "sku": row[1],
        "product_name": row[2],
        "product_type": row[3],
        "category_id": row[4],
        "category_name": row[5],
        "unit_id": row[6],
        "unit_code": row[7],
        "unit_name": row[8],
        "description": row[9],
        "reorder_level": row[10],
        "is_active": bool(row[11]),
        "created_at": row[12],
        "updated_at": row[13],
    }


PRODUCT_SELECT = """SELECT p.ProductID, p.SKU, p.ProductName, p.ProductType,
    p.CategoryID, c.CategoryName, p.UnitID, u.UnitCode, u.UnitName,
    p.Description, p.ReorderLevel, p.IsActive, p.CreatedAt, p.UpdatedAt
    FROM dbo.Products AS p
    LEFT JOIN dbo.ProductCategories AS c
      ON c.CategoryID = p.CategoryID AND c.CompanyID = p.CompanyID
    JOIN dbo.UnitsOfMeasure AS u ON u.UnitID = p.UnitID"""


@app.get("/api/v1/inventory/categories")
def list_categories(user=Depends(require_company_user)):
    with database_connection() as connection, database_cursor(connection) as cursor:
        rows = cursor.execute(
            """SELECT CategoryID, CategoryName, Description
               FROM dbo.ProductCategories WHERE CompanyID = ? ORDER BY CategoryName""",
            user["company_id"],
        ).fetchall()
    return [
        {"category_id": row[0], "category_name": row[1], "description": row[2]}
        for row in rows
    ]


@app.post("/api/v1/inventory/categories", status_code=status.HTTP_201_CREATED)
def create_category(payload: CompanyCategoryCreate, user=Depends(require_company_user)):
    with database_connection() as connection, database_cursor(connection) as cursor:
        try:
            row = cursor.execute(
                """INSERT INTO dbo.ProductCategories (CompanyID, CategoryName, Description)
                   OUTPUT INSERTED.CategoryID, INSERTED.CategoryName, INSERTED.Description
                   VALUES (?, ?, ?)""",
                user["company_id"],
                payload.category_name,
                payload.description,
            ).fetchone()
            connection.commit()
        except pyodbc.IntegrityError as exc:
            duplicate_or_server_error(exc, "category")
    return {"category_id": row[0], "category_name": row[1], "description": row[2]}


@app.get("/api/v1/inventory/units")
def list_units(_user=Depends(require_company_user)):
    with database_connection() as connection, database_cursor(connection) as cursor:
        rows = cursor.execute(
            """SELECT UnitID, UnitCode, UnitName, Symbol
               FROM dbo.UnitsOfMeasure WHERE IsActive = 1 ORDER BY UnitName"""
        ).fetchall()
    return [
        {"unit_id": row[0], "unit_code": row[1], "unit_name": row[2], "symbol": row[3]}
        for row in rows
    ]


@app.get("/api/v1/inventory/products")
def list_products(
    search: str = Query(default="", max_length=120),
    category_id: int | None = Query(default=None, gt=0),
    limit: int = Query(default=25, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    user=Depends(require_company_user),
):
    conditions = ["p.CompanyID = ?"]
    params = [user["company_id"]]
    search = search.strip()
    if search:
        conditions.append("(p.SKU LIKE ? OR p.ProductName LIKE ?)")
        params.extend([f"%{search}%", f"%{search}%"])
    if category_id is not None:
        conditions.append("p.CategoryID = ?")
        params.append(category_id)
    where = " WHERE " + " AND ".join(conditions)
    with database_connection() as connection, database_cursor(connection) as cursor:
        total = cursor.execute(
            f"SELECT COUNT(*) FROM dbo.Products AS p{where}", *params
        ).fetchone()[0]
        rows = cursor.execute(
            f"{PRODUCT_SELECT}{where} ORDER BY p.ProductName, p.ProductID OFFSET ? ROWS FETCH NEXT ? ROWS ONLY",
            *params,
            offset,
            limit,
        ).fetchall()
    return {
        "items": [serialize_product(row) for row in rows],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


def get_company_product(cursor, company_id, product_id):
    row = cursor.execute(
        f"{PRODUCT_SELECT} WHERE p.CompanyID = ? AND p.ProductID = ?",
        company_id,
        product_id,
    ).fetchone()
    if not row:
        # Same response whether the ID is absent or belongs to another tenant.
        raise HTTPException(status_code=404, detail="Product not found.")
    return row


@app.post("/api/v1/inventory/products", status_code=status.HTTP_201_CREATED)
def create_product(payload: ProductCreate, user=Depends(require_company_user)):
    with database_connection() as connection, database_cursor(connection) as cursor:
        ensure_category_for_company(cursor, payload.category_id, user["company_id"])
        ensure_unit_exists(cursor, payload.unit_id)
        try:
            product_id = cursor.execute(
                """INSERT INTO dbo.Products
                   (CompanyID, CategoryID, SKU, ProductName, ProductType, UnitID,
                    Description, ReorderLevel)
                   OUTPUT INSERTED.ProductID
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                user["company_id"],
                payload.category_id,
                payload.sku,
                payload.product_name,
                payload.product_type,
                payload.unit_id,
                payload.description,
                payload.reorder_level,
            ).fetchone()[0]
            row = get_company_product(cursor, user["company_id"], product_id)
            connection.commit()
        except pyodbc.IntegrityError as exc:
            duplicate_or_server_error(exc, "product SKU")
    return serialize_product(row)


@app.get("/api/v1/inventory/products/{product_id}")
def get_product(product_id: int = Path(gt=0), user=Depends(require_company_user)):
    with database_connection() as connection, database_cursor(connection) as cursor:
        row = get_company_product(cursor, user["company_id"], product_id)
    return serialize_product(row)


@app.put("/api/v1/inventory/products/{product_id}")
def update_product(
    payload: ProductUpdate,
    product_id: int = Path(gt=0),
    user=Depends(require_company_user),
):
    values = payload.model_dump(exclude_unset=True)
    if not values:
        raise HTTPException(
            status_code=400, detail="Provide at least one product field to update."
        )
    non_nullable = {"sku", "product_name", "product_type", "unit_id", "reorder_level"}
    if any(values.get(key) is None for key in non_nullable if key in values):
        raise HTTPException(
            status_code=422, detail="Required product fields cannot be empty."
        )
    columns = {
        "sku": "SKU",
        "product_name": "ProductName",
        "product_type": "ProductType",
        "unit_id": "UnitID",
        "category_id": "CategoryID",
        "description": "Description",
        "reorder_level": "ReorderLevel",
    }
    assignments = [f"{columns[name]} = ?" for name in values]
    params = list(values.values())
    assignments.append("UpdatedAt = SYSUTCDATETIME()")
    params.extend([user["company_id"], product_id])
    with database_connection() as connection, database_cursor(connection) as cursor:
        # Verify tenant ownership before any associated category/unit check or mutation.
        get_company_product(cursor, user["company_id"], product_id)
        if "category_id" in values:
            ensure_category_for_company(
                cursor, values["category_id"], user["company_id"]
            )
        if values.get("unit_id") is not None:
            ensure_unit_exists(cursor, values["unit_id"])
        try:
            cursor.execute(
                f"UPDATE dbo.Products SET {', '.join(assignments)} WHERE CompanyID = ? AND ProductID = ?",
                *params,
            )
            row = get_company_product(cursor, user["company_id"], product_id)
            connection.commit()
        except pyodbc.IntegrityError as exc:
            duplicate_or_server_error(exc, "product SKU")
    return serialize_product(row)


@app.patch("/api/v1/inventory/products/{product_id}/status")
def update_product_status(
    payload: ProductStatusUpdate,
    product_id: int = Path(gt=0),
    user=Depends(require_company_user),
):
    with database_connection() as connection, database_cursor(connection) as cursor:
        cursor.execute(
            """UPDATE dbo.Products SET IsActive = ?, UpdatedAt = SYSUTCDATETIME()
               WHERE CompanyID = ? AND ProductID = ?""",
            payload.is_active,
            user["company_id"],
            product_id,
        )
        if cursor.rowcount == 0:
            raise HTTPException(status_code=404, detail="Product not found.")
        row = get_company_product(cursor, user["company_id"], product_id)
        connection.commit()
    return serialize_product(row)
