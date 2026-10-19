# app/modules/auth/router.py
from fastapi import APIRouter, Depends, Request

from app.dependencies.auth import get_current_user
from app.modules.auth import service
from app.modules.auth.schemas import ChangePasswordPayload, LoginPayload

router = APIRouter(tags=["authentication"])


@router.post("/auth/login")
def login(payload: LoginPayload):
    return service.login(payload)


@router.get("/auth/me")
def me(user=Depends(get_current_user)):
    return user


@router.post("/auth/change-password")
def change_password(
    payload: ChangePasswordPayload,
    request: Request,
    user=Depends(get_current_user),
):
    return service.change_password(
        user, payload, request.client.host if request.client else None
    )


@router.get("/dashboard")
def dashboard(user=Depends(get_current_user)):
    return {
        "message": "You have authenticated access to the GBMS workspace.",
        "user": user,
    }
