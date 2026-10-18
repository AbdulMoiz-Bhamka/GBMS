"""JWT and Argon2 helpers. Token claims and password hashing stay unchanged."""

from datetime import datetime, timedelta, timezone

import jwt
from argon2 import PasswordHasher

from app.core.config import JWT_ALGORITHM, JWT_SECRET, TOKEN_MINUTES

password_hasher = PasswordHasher()


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


def user_id_from_token(token):
    claims = jwt.decode(
        token,
        JWT_SECRET,
        algorithms=[JWT_ALGORITHM],
        options={"require": ["sub", "iat", "exp", "type"]},
    )
    if claims.get("type") != "access":
        raise jwt.InvalidTokenError("Invalid token type")
    return int(claims["sub"])
