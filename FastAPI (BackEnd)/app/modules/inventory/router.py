from fastapi import APIRouter, Depends, Path, Query, status

from app.dependencies.permissions import require_company_user
from app.modules.inventory import service
from app.modules.inventory.schemas import (
    CompanyCategoryCreate,
    ProductCreate,
    ProductStatusUpdate,
    ProductUpdate,
)

router = APIRouter(prefix="/inventory", tags=["inventory"])


@router.get("/categories")
def list_categories(user=Depends(require_company_user)):
    return service.list_categories(user["company_id"])


@router.post("/categories", status_code=status.HTTP_201_CREATED)
def create_category(
    payload: CompanyCategoryCreate, user=Depends(require_company_user)
):
    return service.create_category(user["company_id"], payload)


@router.get("/units")
def list_units(_user=Depends(require_company_user)):
    return service.list_units()


@router.get("/products")
def list_products(
    search: str = Query(default="", max_length=120),
    category_id: int | None = Query(default=None, gt=0),
    limit: int = Query(default=25, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    user=Depends(require_company_user),
):
    return service.list_products(
        user["company_id"], search, category_id, limit, offset
    )


@router.post("/products", status_code=status.HTTP_201_CREATED)
def create_product(payload: ProductCreate, user=Depends(require_company_user)):
    return service.create_product(user["company_id"], payload)


@router.get("/products/{product_id}")
def get_product(product_id: int = Path(gt=0), user=Depends(require_company_user)):
    return service.get_product(user["company_id"], product_id)


@router.put("/products/{product_id}")
def update_product(
    payload: ProductUpdate,
    product_id: int = Path(gt=0),
    user=Depends(require_company_user),
):
    return service.update_product(user["company_id"], product_id, payload)


@router.patch("/products/{product_id}/status")
def update_product_status(
    payload: ProductStatusUpdate,
    product_id: int = Path(gt=0),
    user=Depends(require_company_user),
):
    return service.set_product_status(user["company_id"], product_id, payload)
