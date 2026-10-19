"""JWT and Argon2 helpers, including versioned access tokens."""

from datetime import datetime, timedelta, timezone
import secrets
import string

import jwt
from argon2 import PasswordHasher

from app.core.config import JWT_ALGORITHM, JWT_SECRET, TOKEN_MINUTES

password_hasher = PasswordHasher()


def make_token(user, auth_version=0):
    now = datetime.now(timezone.utc)
    return jwt.encode(
        {
            "sub": str(user["user_id"]),
            "iat": now,
            "exp": now + timedelta(minutes=TOKEN_MINUTES),
            "type": "access",
            "ver": int(auth_version),
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
    return int(claims["sub"]), int(claims.get("ver", 0))


def generate_temporary_password(length=24):
    """Generate a one-use temporary password with letters and digits."""
    alphabet = string.ascii_letters + string.digits + "-_"
    characters = [secrets.choice(string.ascii_letters), secrets.choice(string.digits)]
    characters.extend(secrets.choice(alphabet) for _ in range(length - len(characters)))
    secrets.SystemRandom().shuffle(characters)
    return "".join(characters)
