from fastapi import APIRouter, Depends, Path, Query, status

from app.dependencies.auth import get_current_user
from app.modules.users import service
from app.modules.users.schemas import (
    CompanyUserCreate,
    CompanyUserStatusUpdate,
    CompanyUserUpdate,
)

router = APIRouter(tags=["company users"])


@router.get("/users/assignable-options")
def assignable_options(actor=Depends(get_current_user)):
    return service.get_assignable_options(actor)


@router.get("/companies/{company_id}/users")
def list_company_users(
    company_id: int = Path(gt=0),
    search: str = Query(default="", max_length=120),
    actor=Depends(get_current_user),
):
    return service.list_company_users(actor, company_id, search)


@router.post(
    "/companies/{company_id}/users", status_code=status.HTTP_201_CREATED
)
def create_company_user(
    payload: CompanyUserCreate,
    company_id: int = Path(gt=0),
    actor=Depends(get_current_user),
):
    return service.create_company_user(actor, company_id, payload)


@router.get("/companies/{company_id}/users/{user_id}")
def get_company_user(
    company_id: int = Path(gt=0),
    user_id: int = Path(gt=0),
    actor=Depends(get_current_user),
):
    return service.get_company_user(actor, company_id, user_id)


@router.put("/companies/{company_id}/users/{user_id}")
def update_company_user(
    payload: CompanyUserUpdate,
    company_id: int = Path(gt=0),
    user_id: int = Path(gt=0),
    actor=Depends(get_current_user),
):
    return service.update_company_user(actor, company_id, user_id, payload)


@router.patch("/companies/{company_id}/users/{user_id}/status")
def update_company_user_status(
    payload: CompanyUserStatusUpdate,
    company_id: int = Path(gt=0),
    user_id: int = Path(gt=0),
    actor=Depends(get_current_user),
):
    return service.set_company_user_status(
        actor, company_id, user_id, payload.account_status
    )


@router.delete("/companies/{company_id}/users/{user_id}")
def delete_company_user(
    company_id: int = Path(gt=0),
    user_id: int = Path(gt=0),
    actor=Depends(get_current_user),
):
    return service.delete_company_user(actor, company_id, user_id)
