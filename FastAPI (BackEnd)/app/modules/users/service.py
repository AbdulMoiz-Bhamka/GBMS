import logging

import pyodbc
from fastapi import HTTPException

from app.core.security import password_hasher
from app.db.connection import database_connection, database_cursor
from app.modules.roles.service import get_role_id
from app.modules.users import repository

logger = logging.getLogger("gbms")


def public_user(user_id, username, full_name, email, role_name, company_id, company_status):
    return {
        "user_id": user_id,
        "username": username,
        "full_name": full_name,
        "email": email,
        "role_name": role_name,
        "company_id": company_id,
        "company_status": company_status,
    }


def validate_role_company(role_name, company_id, company_status):
    """Use database account assignments, never a client-supplied tenant."""
    if role_name == "SUPER_ADMIN":
        if company_id is not None:
            raise HTTPException(
                status_code=403,
                detail="Platform administrator account configuration is invalid.",
            )
        return
    if company_id is None:
        raise HTTPException(status_code=403, detail="This account is not assigned to a company.")
    if company_status != "ACTIVE":
        raise HTTPException(status_code=403, detail="This company is inactive.")


def get_authenticated_user(user_id):
    unauthorized = HTTPException(
        status_code=401,
        detail="Your session is invalid or has expired.",
        headers={"WWW-Authenticate": "Bearer"},
    )
    with database_connection() as connection, database_cursor(connection) as cursor:
        row = repository.get_auth_user_by_id(cursor, user_id)
    if not row:
        raise unauthorized
    if row[5] != "ACTIVE":
        raise HTTPException(
            status_code=403,
            detail="This account is not active. Contact your administrator.",
        )
    validate_role_company(row[4], row[6], row[7])
    return public_user(*row[:5], row[6], row[7])


def list_company_users(company_id):
    with database_connection() as connection, database_cursor(connection) as cursor:
        company = cursor.execute(
            "SELECT CompanyID FROM dbo.Companies WHERE CompanyID = ?", company_id
        ).fetchone()
        if not company:
            raise HTTPException(status_code=404, detail="Company not found.")
        rows = repository.list_company_users(cursor, company_id)
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


def create_company_user(company_id, payload):
    try:
        with database_connection() as connection, database_cursor(connection) as cursor:
            company = cursor.execute(
                "SELECT CompanyStatus FROM dbo.Companies WHERE CompanyID = ?",
                company_id,
            ).fetchone()
            if not company:
                raise HTTPException(status_code=404, detail="Company not found.")
            if company[0] != "ACTIVE":
                raise HTTPException(
                    status_code=409, detail="Activate the company before creating users."
                )
            role = get_role_id(cursor, payload.role_name)
            if not role:
                logger.error(
                    "Configured company role is missing from dbo.Roles: %s",
                    payload.role_name,
                )
                raise HTTPException(
                    status_code=500,
                    detail="The selected account role is not configured. Contact support.",
                )
            password_hash = password_hasher.hash(payload.password)
            row = repository.insert_company_user(
                cursor, payload, role[0], company_id, password_hash
            )
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
            "Integrity failure creating company user (company_id=%s, role=%s).",
            company_id,
            payload.role_name,
        )
        raise HTTPException(
            status_code=500,
            detail="Could not create the company account because of a database integrity error.",
        ) from exc
    except pyodbc.Error as exc:
        logger.exception(
            "SQL Server error creating company user (company_id=%s, role=%s).",
            company_id,
            payload.role_name,
        )
        raise HTTPException(
            status_code=500,
            detail="Could not create the company account because of a database error. Check the server log.",
        ) from exc
    except Exception as exc:
        logger.exception(
            "Unexpected error creating company user (company_id=%s, role=%s).",
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
