from fastapi import APIRouter, Depends, Path, Query
from app.dependencies.permissions import require_company_permission
from app.modules.goods_receipts import service
from app.modules.goods_receipts.schemas import GoodsReceiptCreate

router = APIRouter(prefix="/goods-receipts", tags=["goods receipts and material lots"])

@router.get("/options")
def options(purchase_order_id: int | None = Query(default=None, gt=0),
            user=Depends(require_company_permission("inventory.stock.receive"))):
    return service.receipt_options(user["company_id"], purchase_order_id)

@router.post("", status_code=201)
def create_receipt(payload: GoodsReceiptCreate, user=Depends(require_company_permission("inventory.stock.receive"))):
    return service.create_receipt(user["company_id"], user["user_id"], payload)

@router.get("/lots")
def list_lots(product_id: int | None = Query(default=None, gt=0),
              user=Depends(require_company_permission("inventory.view"))):
    return {"items": service.list_material_lots(user["company_id"], product_id)}

@router.get("/lots/{lot_id}/label")
def get_lot_label(lot_id: int = Path(gt=0),
                  user=Depends(require_company_permission("inventory.barcode.manage"))):
    return service.barcode_label(user["company_id"], lot_id)

@router.get("/lots/{lot_id}")
def get_lot(lot_id: int = Path(gt=0),
            user=Depends(require_company_permission("inventory.view"))):
    rows = service.list_material_lots(user["company_id"])
    lot = next((row for row in rows if row["material_lot_id"] == lot_id), None)
    if not lot:
        from fastapi import HTTPException
        raise HTTPException(404, "Material lot not found for this company.")
    return lot

@router.get("/barcode/{barcode_value}")
def lookup_by_barcode(
    barcode_value: str = Path(min_length=1, max_length=64, pattern=r"^[A-Za-z0-9-]+$"),
    user=Depends(require_company_permission("inventory.view")),
):
    """Resolve any BarcodeRegistry entry by its value. Returns entity type and details."""
    return service.lookup_barcode(user["company_id"], barcode_value)
