from datetime import date
from typing import Literal

from fastapi import APIRouter, Depends, Path, Query, status

from app.dependencies.permissions import require_company_permission
from app.modules.inventory import service
from app.modules.inventory.schemas import (
    CompanyCategoryCreate,
    ProductCreate,
    ProductStatusUpdate,
    ProductUpdate,
    StockAdjustmentCreate,
    StockIssueCreate,
    StockReceiptCreate,
)

router = APIRouter(prefix="/inventory", tags=["inventory"])


@router.get("/categories")
def list_categories(user=Depends(require_company_permission("inventory.view"))):
    return service.list_categories(user["company_id"])


@router.post("/categories", status_code=status.HTTP_201_CREATED)
def create_category(
    payload: CompanyCategoryCreate, user=Depends(require_company_permission("inventory.create"))
):
    return service.create_category(user["company_id"], payload)


@router.get("/units")
def list_units(_user=Depends(require_company_permission("inventory.view"))):
    return service.list_units()


@router.get("/products")
def list_products(
    search: str = Query(default="", max_length=120),
    category_id: int | None = Query(default=None, gt=0),
    limit: int = Query(default=25, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    low_stock_only: bool = Query(default=False),
    sort_by: Literal["name", "quantity", "reorder_level"] = Query(default="name"),
    product_type: Literal["RAW_MATERIAL", "FINISHED_GOOD"] | None = Query(default=None),
    user=Depends(require_company_permission("inventory.view")),
):
    return service.list_products(
        user["company_id"], search, category_id, limit, offset, low_stock_only, sort_by, product_type
    )


@router.post("/products", status_code=status.HTTP_201_CREATED)
def create_product(payload: ProductCreate, user=Depends(require_company_permission("inventory.create"))):
    return service.create_product(user["company_id"], user["user_id"], payload)


@router.get("/low-stock/count")
def get_low_stock_count(user=Depends(require_company_permission("inventory.view"))):
    return service.low_stock_count(user["company_id"])


@router.get("/products/{product_id}")
def get_product(product_id: int = Path(gt=0), user=Depends(require_company_permission("inventory.view"))):
    return service.get_product(user["company_id"], product_id)


@router.put("/products/{product_id}")
def update_product(
    payload: ProductUpdate,
    product_id: int = Path(gt=0),
    user=Depends(require_company_permission("inventory.update")),
):
    return service.update_product(user["company_id"], product_id, payload)


@router.patch("/products/{product_id}/status")
def update_product_status(
    payload: ProductStatusUpdate,
    product_id: int = Path(gt=0),
    user=Depends(require_company_permission("inventory.update")),
):
    return service.set_product_status(user["company_id"], product_id, payload)


@router.post("/products/{product_id}/stock/receipts", status_code=status.HTTP_201_CREATED)
def receive_stock(
    payload: StockReceiptCreate,
    product_id: int = Path(gt=0),
    user=Depends(require_company_permission("inventory.stock.receive")),
):
    return service.record_stock_transaction(
        user["company_id"], product_id, user["user_id"],
        transaction_type="STOCK_RECEIPT", quantity_changed=payload.received_quantity,
        supplier_id=payload.supplier_id, purchase_order_id=payload.purchase_order_id,
        reference_number=payload.reference_number, notes=payload.notes,
        idempotency_key=payload.idempotency_key,
    )


@router.post("/products/{product_id}/stock/issues", status_code=status.HTTP_201_CREATED)
def issue_stock(
    payload: StockIssueCreate,
    product_id: int = Path(gt=0),
    user=Depends(require_company_permission("inventory.stock.issue")),
):
    return service.record_stock_transaction(
        user["company_id"], product_id, user["user_id"],
        transaction_type="STOCK_ISSUE", quantity_changed=-payload.issued_quantity,
        reference_number=payload.reference_number, notes=payload.notes,
        idempotency_key=payload.idempotency_key,
    )


@router.post("/products/{product_id}/stock/adjustments", status_code=status.HTTP_201_CREATED)
def adjust_stock(
    payload: StockAdjustmentCreate,
    product_id: int = Path(gt=0),
    user=Depends(require_company_permission("inventory.stock.adjust")),
):
    return service.record_stock_transaction(
        user["company_id"], product_id, user["user_id"],
        transaction_type="STOCK_ADJUSTMENT", quantity_changed=payload.quantity_delta,
        reference_number=payload.reference_number, notes=payload.notes,
        idempotency_key=payload.idempotency_key,
    )


@router.get("/products/{product_id}/stock/transactions")
def get_stock_history(
    product_id: int = Path(gt=0),
    transaction_type: Literal[
        "OPENING_STOCK", "STOCK_RECEIPT", "STOCK_ISSUE", "GOODS_RECEIPT",
        "MATERIAL_ISSUE", "MATERIAL_CONSUMPTION", "PRODUCTION_CONSUMPTION",
        "PRODUCTION_OUTPUT", "STOCK_ADJUSTMENT",
    ] | None = Query(default=None),
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    user=Depends(require_company_permission("inventory.view")),
):
    return service.stock_transaction_history(
        user["company_id"], product_id, transaction_type, date_from, date_to, limit, offset
    )


@router.post("/products/{product_id}/barcode")
def generate_product_barcode(
    product_id: int = Path(gt=0),
    user=Depends(require_company_permission("inventory.barcode.manage")),
):
    return service.generate_product_barcode(user["company_id"], product_id, user["user_id"])


@router.get("/products/{product_id}/barcode")
def get_product_barcode_label(
    product_id: int = Path(gt=0),
    user=Depends(require_company_permission("inventory.barcode.manage")),
):
    return service.get_product_barcode_label(user["company_id"], product_id)


@router.get("/barcodes/{barcode_value}")
def lookup_barcode(
    barcode_value: str = Path(min_length=1, max_length=64, pattern=r"^[A-Za-z0-9-]+$"),
    user=Depends(require_company_permission("inventory.view")),
):
    return service.lookup_product_barcode(user["company_id"], barcode_value)
