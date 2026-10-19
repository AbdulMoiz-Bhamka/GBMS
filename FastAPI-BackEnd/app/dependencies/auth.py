import jwt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.security import user_id_from_token
from app.modules.users.service import get_authenticated_user

bearer_scheme = HTTPBearer(auto_error=False, scheme_name="BearerAuth")


def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
):
    unauthorized = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Your session is invalid or has expired.",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise unauthorized
    try:
        user_id, token_version = user_id_from_token(credentials.credentials)
    except (jwt.PyJWTError, ValueError, TypeError) as exc:
        raise unauthorized from exc
    user = get_authenticated_user(user_id, token_version)
    if user["must_change_password"] and not (
        request.method == "POST" and request.url.path == "/api/v1/auth/change-password"
    ) and not (request.method == "GET" and request.url.path == "/api/v1/auth/me"):
        raise HTTPException(
            status_code=403,
            detail="You must change your temporary password before using GBMS.",
        )
    return user
