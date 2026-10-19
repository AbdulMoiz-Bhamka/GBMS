from typing import Literal

from fastapi import APIRouter, Depends, Path, Query, status

from app.dependencies.permissions import require_company_permission
from app.modules.suppliers import service
from app.modules.suppliers.schemas import (
    SupplierCreate,
    SupplierStatusUpdate,
    SupplierUpdate,
)

router = APIRouter(prefix="/suppliers", tags=["suppliers"])


@router.get("")
def list_suppliers(
    search: str = Query(default="", max_length=120),
    supplier_status: Literal["ACTIVE", "INACTIVE"] | None = Query(default=None),
    limit: int = Query(default=25, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    user=Depends(require_company_permission("suppliers.view")),
):
    return service.list_suppliers(
        user["company_id"], search, supplier_status, limit, offset
    )


@router.post("", status_code=status.HTTP_201_CREATED)
def create_supplier(
    payload: SupplierCreate,
    user=Depends(require_company_permission("suppliers.create")),
):
    return service.create_supplier(user["company_id"], payload)


@router.get("/{supplier_id}")
def get_supplier(
    supplier_id: int = Path(gt=0),
    user=Depends(require_company_permission("suppliers.view")),
):
    return service.get_supplier(user["company_id"], supplier_id)


@router.put("/{supplier_id}")
def update_supplier(
    payload: SupplierUpdate,
    supplier_id: int = Path(gt=0),
    user=Depends(require_company_permission("suppliers.update")),
):
    return service.update_supplier(user["company_id"], supplier_id, payload)


@router.patch("/{supplier_id}/status")
def update_supplier_status(
    payload: SupplierStatusUpdate,
    supplier_id: int = Path(gt=0),
    user=Depends(require_company_permission("suppliers.deactivate")),
):
    return service.set_supplier_status(
        user["company_id"], supplier_id, payload.supplier_status
    )
