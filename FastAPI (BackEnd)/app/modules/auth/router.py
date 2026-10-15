# app/modules/auth/router.py
from fastapi import APIRouter, Depends

from app.dependencies.auth import get_current_user
from app.modules.auth import service
from app.modules.auth.schemas import LoginPayload

router = APIRouter(tags=["authentication"])


@router.post("/auth/login")
def login(payload: LoginPayload):
    return service.login(payload)


@router.get("/auth/me")
def me(user=Depends(get_current_user)):
    return user


@router.get("/dashboard")
def dashboard(user=Depends(get_current_user)):
    return {
        "message": "You have authenticated access to the GBMS workspace.",
        "user": user,
    }
