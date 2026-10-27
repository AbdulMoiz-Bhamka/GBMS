from fastapi import APIRouter, Depends, Path, Query, status

from app.dependencies.permissions import require_company_permission
from app.modules.inventory import service
from app.modules.inventory.schemas import (
    CompanyCategoryCreate,
    ProductCreate,
    ProductStatusUpdate,
    ProductUpdate,
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
    user=Depends(require_company_permission("inventory.view")),
):
    return service.list_products(
        user["company_id"], search, category_id, limit, offset
    )


@router.post("/products", status_code=status.HTTP_201_CREATED)
def create_product(payload: ProductCreate, user=Depends(require_company_permission("inventory.create"))):
    return service.create_product(user["company_id"], payload)


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


@router.post("/products/{product_id}/barcode")
def generate_product_barcode(
    product_id: int = Path(gt=0),
    user=Depends(require_company_permission("inventory.barcode.manage")),
):
    return service.generate_product_barcode(user["company_id"], product_id)


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
