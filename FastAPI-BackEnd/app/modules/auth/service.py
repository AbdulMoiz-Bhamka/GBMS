from datetime import datetime, timezone

from argon2.exceptions import VerificationError, VerifyMismatchError
from fastapi import HTTPException

from app.core.config import TOKEN_MINUTES
from app.core.security import make_token, password_hasher
from app.db.connection import database_connection, database_cursor
from app.modules.users import repository
from app.modules.users.service import (
    permissions_for_user,
    public_user,
    validate_role_company,
)


def login(payload):
    with database_connection() as connection, database_cursor(connection) as cursor:
        row = repository.get_login_user_by_username(cursor, payload.username.strip())
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
        if row[10] and (
            row[12] is None
            or row[12] <= datetime.now(timezone.utc).replace(tzinfo=None)
        ):
            raise HTTPException(
                status_code=403,
                detail="This temporary password has expired. Contact your administrator for a new reset.",
            )
        validate_role_company(row[4], row[7], row[8])
        permissions = permissions_for_user(cursor, row[0], row[4], row[9])
    user = public_user(*row[:5], row[7], row[8], permissions, bool(row[10]))
    return {
        "access_token": make_token(user, row[11]),
        "token_type": "bearer",
        "expires_in": TOKEN_MINUTES * 60,
        "user": user,
    }


def change_password(user, payload, source_ip=None):
    with database_connection() as connection, database_cursor(connection) as cursor:
        credentials = repository.get_password_credentials(cursor, user["user_id"])
        if not credentials:
            raise HTTPException(status_code=401, detail="Your session is invalid or has expired.")
        current_hash, _must_change_password, auth_version = credentials
        try:
            password_hasher.verify(current_hash, payload.current_password)
        except (VerifyMismatchError, VerificationError, ValueError) as exc:
            raise HTTPException(status_code=400, detail="Current password is incorrect.") from exc
        try:
            if password_hasher.verify(current_hash, payload.new_password):
                raise HTTPException(status_code=400, detail="New password must be different from your current password.")
        except (VerifyMismatchError, VerificationError, ValueError):
            pass

        new_hash = password_hasher.hash(payload.new_password)
        result = repository.update_own_password(
            cursor, user["user_id"], auth_version, new_hash
        )
        if result.rowcount != 1:
            raise HTTPException(status_code=409, detail="Password changed in another session. Sign in again.")
        repository.insert_password_audit(
            cursor, user["user_id"], user["user_id"], "PASSWORD_CHANGED", source_ip
        )
        connection.commit()
    return {"password_changed": True, "sessions_invalidated": True}
