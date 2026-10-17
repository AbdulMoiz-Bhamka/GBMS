from fastapi import HTTPException
from argon2.exceptions import VerificationError, VerifyMismatchError

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
        validate_role_company(row[4], row[7], row[8])
        permissions = permissions_for_user(cursor, row[0], row[4], row[9])
    user = public_user(*row[:5], row[7], row[8], permissions)
    return {
        "access_token": make_token(user),
        "token_type": "bearer",
        "expires_in": TOKEN_MINUTES * 60,
        "user": user,
    }
