from datetime import date
from typing import Literal

from fastapi import APIRouter, Depends, Path, Query, status

from app.dependencies.permissions import require_company_permission
from app.modules.purchasing import service
from app.modules.purchasing.schemas import PurchaseOrderCancel, PurchaseOrderDraft

router = APIRouter(prefix="/purchase-orders", tags=["purchase orders"])


@router.get("/form-options")
def purchase_order_form_options(
    user=Depends(require_company_permission("purchasing.view")),
):
    return service.order_form_options(user["company_id"])


@router.get("")
def list_purchase_orders(
    search: str = Query(default="", max_length=80),
    supplier_id: int | None = Query(default=None, gt=0),
    order_status: Literal["DRAFT", "SUBMITTED", "PARTIALLY_RECEIVED", "COMPLETED", "CANCELLED"] | None = Query(default=None, alias="status"),
    date_from: date | None = None,
    date_to: date | None = None,
    limit: int = Query(default=25, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    user=Depends(require_company_permission("purchasing.view")),
):
    return service.list_orders(user["company_id"], search, supplier_id,
                               order_status, date_from, date_to, limit, offset)


@router.post("", status_code=status.HTTP_201_CREATED)
def create_purchase_order(
    payload: PurchaseOrderDraft,
    user=Depends(require_company_permission("purchasing.create")),
):
    return service.create_draft(user["company_id"], user["user_id"], payload)


@router.get("/{purchase_order_id}")
def get_purchase_order(
    purchase_order_id: int = Path(gt=0),
    user=Depends(require_company_permission("purchasing.view")),
):
    return service.get_order(user["company_id"], purchase_order_id)


@router.get("/{purchase_order_id}/print")
def get_printable_purchase_order(
    purchase_order_id: int = Path(gt=0),
    user=Depends(require_company_permission("purchasing.view")),
):
    return service.get_order(user["company_id"], purchase_order_id)


@router.put("/{purchase_order_id}")
def update_purchase_order(
    payload: PurchaseOrderDraft,
    purchase_order_id: int = Path(gt=0),
    user=Depends(require_company_permission("purchasing.update")),
):
    return service.update_draft(user["company_id"], purchase_order_id, payload)


@router.post("/{purchase_order_id}/submit")
def submit_purchase_order(
    purchase_order_id: int = Path(gt=0),
    user=Depends(require_company_permission("purchasing.submit")),
):
    return service.submit_order(user["company_id"], user["user_id"], purchase_order_id)


@router.post("/{purchase_order_id}/cancel")
def cancel_purchase_order(
    payload: PurchaseOrderCancel,
    purchase_order_id: int = Path(gt=0),
    user=Depends(require_company_permission("purchasing.cancel")),
):
    return service.cancel_order(user["company_id"], user["user_id"],
                                purchase_order_id, payload.note)
