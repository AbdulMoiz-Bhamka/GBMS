from fastapi import APIRouter, Depends, Path, status

from app.dependencies.permissions import require_super_admin
from app.modules.users import service
from app.modules.users.schemas import CompanyUserCreate

router = APIRouter(tags=["company users"])


@router.get("/companies/{company_id}/users")
def list_company_users(
    company_id: int = Path(gt=0), _admin=Depends(require_super_admin)
):
    return service.list_company_users(company_id)


@router.post(
    "/companies/{company_id}/users", status_code=status.HTTP_201_CREATED
)
def create_company_user(
    payload: CompanyUserCreate,
    company_id: int = Path(gt=0),
    _admin=Depends(require_super_admin),
):
    return service.create_company_user(company_id, payload)
