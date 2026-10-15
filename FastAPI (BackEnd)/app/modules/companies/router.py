# app/modules/companies/router.py
from fastapi import APIRouter, Depends, Path, Query, status

from app.dependencies.permissions import require_super_admin
from app.modules.companies import service
from app.modules.companies.schemas import CompanyCreate, CompanyStatusUpdate, CompanyUpdate

router = APIRouter(tags=["companies"])


@router.get("/companies")
def list_companies(
    search: str = Query(default="", max_length=120),
    limit: int = Query(default=25, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    _admin=Depends(require_super_admin),
):
    return service.list_companies(search, limit, offset)


@router.post("/companies", status_code=status.HTTP_201_CREATED)
def create_company(payload: CompanyCreate, _admin=Depends(require_super_admin)):
    return service.create_company(payload)


@router.get("/companies/{company_id}")
def get_company(company_id: int = Path(gt=0), _admin=Depends(require_super_admin)):
    return service.get_company(company_id)


@router.put("/companies/{company_id}")
def update_company(
    payload: CompanyUpdate,
    company_id: int = Path(gt=0),
    _admin=Depends(require_super_admin),
):
    return service.update_company(company_id, payload)


@router.patch("/companies/{company_id}/status")
def update_company_status(
    payload: CompanyStatusUpdate,
    company_id: int = Path(gt=0),
    _admin=Depends(require_super_admin),
):
    return service.set_company_status(company_id, payload)
