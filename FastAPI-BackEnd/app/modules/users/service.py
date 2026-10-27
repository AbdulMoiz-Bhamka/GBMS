import logging

import pyodbc
from fastapi import HTTPException

from app.core.permissions import (
    ALL_PERMISSIONS,
    COMPANY_USER_ROLES,
    PERMISSION_LABELS,
    effective_permissions,
    has_permission,
)
from app.core.security import generate_temporary_password, password_hasher
from app.db.connection import database_connection, database_cursor
from app.modules.roles.service import get_role_id
from app.modules.users import repository

logger = logging.getLogger("gbms")


def public_user(
    user_id,
    username,
    full_name,
    email,
    role_name,
    company_id,
    company_status,
    permissions=(),
    must_change_password=False,
):
    return {
        "user_id": user_id,
        "username": username,
        "full_name": full_name,
        "email": email,
        "role_name": role_name,
        "company_id": company_id,
        "company_status": company_status,
        "permissions": list(permissions),
        "must_change_password": bool(must_change_password),
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


def permissions_for_user(cursor, user_id, role_name, configured):
    assigned = [row[0] for row in repository.list_user_permissions(cursor, user_id)]
    return effective_permissions(role_name, bool(configured), assigned)


def get_authenticated_user(user_id, token_version=0):
    unauthorized = HTTPException(
        status_code=401,
        detail="Your session is invalid or has expired.",
        headers={"WWW-Authenticate": "Bearer"},
    )
    with database_connection() as connection, database_cursor(connection) as cursor:
        row = repository.get_auth_user_by_id(cursor, user_id)
        if not row:
            raise unauthorized
        if int(row[10]) != token_version:
            raise unauthorized
        if row[5] != "ACTIVE":
            raise HTTPException(
                status_code=403,
                detail="This account is not active. Contact your administrator.",
            )
        validate_role_company(row[4], row[6], row[7])
        permissions = permissions_for_user(cursor, row[0], row[4], row[8])
    return public_user(*row[:5], row[6], row[7], permissions, bool(row[9]))


def reset_company_user_password(actor, company_id, user_id, source_ip=None):
    company_id = _company_for_actor(actor, company_id)
    _require(actor, "users.update")
    if user_id == actor.get("user_id"):
        raise HTTPException(status_code=400, detail="Use Change password to update your own password.")

    with database_connection() as connection, database_cursor(connection) as cursor:
        existing = repository.get_company_user(cursor, company_id, user_id)
        if not existing:
            raise HTTPException(status_code=404, detail="User not found.")
        target_role = existing[4]
        if target_role == "SUPER_ADMIN":
            raise HTTPException(status_code=403, detail="Super Admin credentials cannot be reset here.")
        if target_role == "COMPANY_ADMIN" and actor["role_name"] != "SUPER_ADMIN":
            raise HTTPException(status_code=403, detail="Only the Super Admin can help recover a Company Admin account.")
        if target_role not in COMPANY_USER_ROLES and target_role != "COMPANY_ADMIN":
            raise HTTPException(status_code=403, detail="This account role cannot be reset through company user management.")

        temporary_password = generate_temporary_password()
        password_hash = password_hasher.hash(temporary_password)
        result = repository.reset_company_user_password(
            cursor, company_id, user_id, password_hash
        )
        if result.rowcount != 1:
            raise HTTPException(status_code=404, detail="User not found.")
        actor_id = actor.get("user_id")
        event_type = (
            "PASSWORD_RESET_BY_SUPER_ADMIN"
            if actor["role_name"] == "SUPER_ADMIN"
            else "PASSWORD_RESET_BY_COMPANY_ADMIN"
        )
        repository.insert_password_audit(
            cursor, user_id, actor_id, event_type, source_ip
        )
        connection.commit()

    return {
        "user_id": user_id,
        "username": existing[1],
        "temporary_password": temporary_password,
        "must_change_password": True,
    }


def _company_for_actor(actor, requested_company_id):
    if actor["role_name"] == "SUPER_ADMIN":
        return requested_company_id
    if actor.get("company_id") != requested_company_id:
        raise HTTPException(status_code=404, detail="Company not found.")
    return actor["company_id"]


def _require(actor, permission_code):
    if actor["role_name"] != "SUPER_ADMIN" and not has_permission(actor, permission_code):
        raise HTTPException(status_code=403, detail=f"Permission required: {permission_code}.")


def _validate_permissions(permission_codes):
    codes = set(permission_codes or ())
    unknown = codes.difference(ALL_PERMISSIONS)
    if unknown:
        raise HTTPException(status_code=422, detail="One or more selected permissions are invalid.")
    return codes


def _validate_grant(actor, permission_codes):
    codes = _validate_permissions(permission_codes)
    if actor["role_name"] != "SUPER_ADMIN" and not codes.issubset(set(actor.get("permissions", ()))):
        raise HTTPException(status_code=403, detail="You cannot grant permissions you do not have.")
    return codes


def _serialize_user(cursor, row):
    permissions = permissions_for_user(cursor, row[0], row[4], row[8])
    return {
        "user_id": row[0],
        "username": row[1],
        "full_name": row[2],
        "email": row[3],
        "role_name": row[4],
        "account_status": row[5],
        "company_id": row[6],
        "created_at": row[7],
        "permission_codes": permissions,
    }


def list_company_users(actor, company_id, search=""):
    company_id = _company_for_actor(actor, company_id)
    _require(actor, "users.view")
    with database_connection() as connection, database_cursor(connection) as cursor:
        company = cursor.execute(
            "SELECT CompanyID FROM dbo.Companies WHERE CompanyID = ?", company_id
        ).fetchone()
        if not company:
            raise HTTPException(status_code=404, detail="Company not found.")
        rows = repository.list_company_users(cursor, company_id, search.strip())
        users = [_serialize_user(cursor, repository.get_company_user(cursor, company_id, row[0])) for row in rows]
    return {"items": users, "total": len(users)}


def get_company_user(actor, company_id, user_id):
    company_id = _company_for_actor(actor, company_id)
    _require(actor, "users.view")
    with database_connection() as connection, database_cursor(connection) as cursor:
        row = repository.get_company_user(cursor, company_id, user_id)
        if not row:
            raise HTTPException(status_code=404, detail="User not found.")
        return _serialize_user(cursor, row)


def get_assignable_options(actor):
    _require(actor, "users.assign_role")
    return {
        "roles": list(COMPANY_USER_ROLES),
        "permissions": [
            {"code": code, "label": label} for code, label in PERMISSION_LABELS.items()
            if code not in {"dashboard.view", "dashboard.company_overview"}
        ],
    }


def create_company_user(actor, company_id, payload):
    company_id = _company_for_actor(actor, company_id)
    _require(actor, "users.create")
    if actor["role_name"] != "SUPER_ADMIN":
        _require(actor, "users.assign_role")
        if payload.role_name not in COMPANY_USER_ROLES:
            raise HTTPException(status_code=403, detail="You cannot assign that role.")
    if payload.role_name == "COMPANY_ADMIN" and payload.permission_codes:
        raise HTTPException(
            status_code=422,
            detail="Company Admin access is fixed to the full company role defaults. Use another role for limited access.",
        )
    permissions = _validate_grant(actor, payload.permission_codes)
    # Company Admin permissions come from the role defaults, not user grants.
    permissions_configured = payload.role_name != "COMPANY_ADMIN"
    if payload.role_name == "COMPANY_ADMIN":
        permissions = set()
    if payload.role_name == "WORKER" and permissions:
        raise HTTPException(
            status_code=422,
            detail="Worker accounts can only access their dashboard.",
        )
    try:
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
            role = get_role_id(cursor, payload.role_name)
            if not role:
                logger.error("Configured company role is missing from dbo.Roles: %s", payload.role_name)
                raise HTTPException(
                    status_code=500,
                    detail="The selected account role is not configured. Contact support.",
                )
            password_hash = password_hasher.hash(payload.password)
            user_id = repository.insert_company_user(
                cursor,
                payload,
                role[0],
                company_id,
                password_hash,
                permissions_configured=permissions_configured,
            )
            if permissions_configured:
                repository.replace_user_permissions(
                    cursor, user_id, permissions, actor["user_id"]
                )
            row = repository.get_company_user(cursor, company_id, user_id)
            connection.commit()
            result = _serialize_user(cursor, row)
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
        logger.exception("Integrity failure creating company user (company_id=%s).", company_id)
        raise HTTPException(status_code=500, detail="Could not create the company user.") from exc
    except pyodbc.Error as exc:
        logger.exception("SQL Server error creating company user (company_id=%s).", company_id)
        raise HTTPException(status_code=500, detail="Could not create the company user due to a database error.") from exc
    return result


def update_company_user(actor, company_id, user_id, payload):
    company_id = _company_for_actor(actor, company_id)
    _require(actor, "users.update")
    values = payload.model_dump(exclude_unset=True)
    if not values:
        raise HTTPException(status_code=400, detail="Provide at least one user field to update.")
    if any(values.get(field) is None for field in ("username", "full_name", "email") if field in values):
        raise HTTPException(status_code=422, detail="Username, full name, and email cannot be empty.")
    permission_codes = values.pop("permission_codes", None)
    role_name = values.pop("role_name", None)
    if user_id == actor.get("user_id") and (permission_codes is not None or role_name is not None):
        raise HTTPException(status_code=403, detail="You cannot change your own role or permissions.")
    if permission_codes is not None or role_name is not None:
        _require(actor, "users.assign_role")
    permissions = _validate_grant(actor, permission_codes) if permission_codes is not None else None
    if role_name == "WORKER" and permissions:
        raise HTTPException(
            status_code=422,
            detail="Worker accounts can only access their dashboard.",
        )
    if role_name is not None and permission_codes is None:
        raise HTTPException(
            status_code=422,
            detail="Provide the permission_codes when changing a user's role.",
        )
    with database_connection() as connection, database_cursor(connection) as cursor:
        existing = repository.get_company_user(cursor, company_id, user_id)
        if not existing:
            raise HTTPException(status_code=404, detail="User not found.")
        if role_name:
            if role_name not in COMPANY_USER_ROLES:
                raise HTTPException(status_code=403, detail="You cannot assign that role.")
            role = get_role_id(cursor, role_name)
            if not role:
                raise HTTPException(status_code=422, detail="The selected role is not configured.")
            values["role_id"] = role[0]
        if permissions is not None:
            values["permissions_configured"] = 1
        try:
            repository.update_company_user(cursor, company_id, user_id, values)
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
            raise
        if permissions is not None:
            repository.replace_user_permissions(cursor, user_id, permissions, actor["user_id"])
        updated = repository.get_company_user(cursor, company_id, user_id)
        connection.commit()
        return _serialize_user(cursor, updated)


def set_company_user_status(actor, company_id, user_id, account_status):
    company_id = _company_for_actor(actor, company_id)
    _require(actor, "users.deactivate")
    if user_id == actor.get("user_id") and account_status != "ACTIVE":
        raise HTTPException(status_code=400, detail="You cannot deactivate your own account.")
    with database_connection() as connection, database_cursor(connection) as cursor:
        existing = repository.get_company_user(cursor, company_id, user_id)
        if not existing:
            raise HTTPException(status_code=404, detail="User not found.")
        repository.update_company_user_status(cursor, company_id, user_id, account_status)
        row = repository.get_company_user(cursor, company_id, user_id)
        connection.commit()
        return _serialize_user(cursor, row)


def delete_company_user(actor, company_id, user_id):
    company_id = _company_for_actor(actor, company_id)
    _require(actor, "users.delete")
    if user_id == actor.get("user_id"):
        raise HTTPException(status_code=400, detail="You cannot delete your own account.")
    try:
        with database_connection() as connection, database_cursor(connection) as cursor:
            existing = repository.get_company_user(cursor, company_id, user_id)
            if not existing:
                raise HTTPException(status_code=404, detail="User not found.")
            repository.delete_company_user(cursor, company_id, user_id)
            connection.commit()
    except HTTPException:
        raise
    except pyodbc.IntegrityError as exc:
        logger.exception(
            "Could not permanently delete company user (company_id=%s, user_id=%s).",
            company_id,
            user_id,
        )
        raise HTTPException(
            status_code=409,
            detail="This user is linked to existing records and cannot be permanently deleted. Deactivate the account instead.",
        ) from exc
    return {"deleted": True, "user_id": user_id}
