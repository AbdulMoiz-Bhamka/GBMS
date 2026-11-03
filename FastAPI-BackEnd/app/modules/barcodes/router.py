from decimal import Decimal
import pyodbc
from pydantic import BaseModel, ConfigDict, Field
from fastapi import APIRouter, Depends, HTTPException, Query
from app.dependencies.permissions import require_company_permission
from app.db.connection import database_connection, database_cursor
from app.modules.inventory import service as inventory_service
from app.core.config import SKU_PATTERN

router = APIRouter(prefix="/barcodes", tags=["finished-goods barcodes"])

class MaterialComponent(BaseModel):
    product_id: int = Field(gt=0)
    quantity_per_finished_unit: Decimal = Field(gt=0, max_digits=18, decimal_places=6)

class MaterialPlanUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    materials: list[MaterialComponent] = Field(default_factory=list, max_length=100)

class FinishedGoodCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    sku: str = Field(min_length=1, max_length=60, pattern=SKU_PATTERN)
    product_name: str = Field(min_length=1, max_length=180)
    unit_id: int = Field(gt=0)
    category_id: int | None = Field(default=None, gt=0)
    description: str | None = Field(default=None, max_length=1000)
    design: str | None = Field(default=None, max_length=100)
    size: str | None = Field(default=None, max_length=40)
    color: str | None = Field(default=None, max_length=50)
    selling_price: Decimal = Field(ge=0, max_digits=18, decimal_places=2)
    materials: list[MaterialComponent] = Field(default_factory=list, max_length=100)

@router.post("", status_code=201)
def create_finished_good(payload: FinishedGoodCreate,
                         user=Depends(require_company_permission("inventory.create"))):
    company_id, actor_id = user["company_id"], user["user_id"]
    component_ids = [component.product_id for component in payload.materials]
    if len(component_ids) != len(set(component_ids)):
        raise HTTPException(422,"A raw material can be included only once.")
    with database_connection() as conn, database_cursor(conn) as cur:
        if payload.category_id is not None and not cur.execute("SELECT 1 FROM dbo.ProductCategories WHERE CompanyID=? AND CategoryID=?",company_id,payload.category_id).fetchone():
            raise HTTPException(422,"Category is not available to this company.")
        if not cur.execute("SELECT 1 FROM dbo.UnitsOfMeasure WHERE UnitID=? AND IsActive=1",payload.unit_id).fetchone():
            raise HTTPException(422,"Select an active unit.")
        for component in payload.materials:
            valid=cur.execute("SELECT 1 FROM dbo.Products WHERE CompanyID=? AND ProductID=? AND ProductType=N'RAW_MATERIAL' AND IsActive=1",company_id,component.product_id).fetchone()
            if not valid: raise HTTPException(422,"Every component must be an active raw material in your company.")
        try:
            pid=cur.execute("""INSERT INTO dbo.Products(CompanyID,CategoryID,SKU,ProductName,ProductType,UnitID,Description,ReorderLevel,QuantityOnHand,VariantDesign,VariantSize,VariantColor,SellingPrice)
              OUTPUT INSERTED.ProductID VALUES(?,?,?, ?,N'FINISHED_GOOD',?,?,0,0,?,?,?,?)""",
              company_id,payload.category_id,payload.sku.strip().upper(),payload.product_name.strip(),payload.unit_id,payload.description,
              payload.design,payload.size,payload.color,payload.selling_price).fetchone()[0]
            for component in payload.materials:
                cur.execute("INSERT INTO dbo.FinishedGoodMaterialComponents(CompanyID,FinishedGoodProductID,RawMaterialProductID,QuantityPerFinishedUnit,CreatedByUserID) VALUES(?,?,?,?,?)",
                    company_id,pid,component.product_id,component.quantity_per_finished_unit,actor_id)
            conn.commit()
        except pyodbc.IntegrityError as exc:
            conn.rollback()
            if "2601" in str(exc) or "2627" in str(exc):
                raise HTTPException(409,"That SKU is already used by a product in this company.") from exc
            raise
        except Exception:
            conn.rollback(); raise
    return {"product_id":pid,"quantity_on_hand":0,"barcode_value":None}


@router.get("")
def list_finished_goods(search: str = Query(default="", max_length=120),
                        category_id: int | None = Query(default=None, gt=0),
                        size: str | None = Query(default=None, max_length=40),
                        color: str | None = Query(default=None, max_length=50),
                        status: str = Query(default="ALL", pattern="^(ALL|ACTIVE|INACTIVE)$"),
                        limit: int = Query(default=100, ge=1, le=500), offset: int = Query(default=0, ge=0),
                        user=Depends(require_company_permission("inventory.barcode.manage"))):
    clauses = ["p.CompanyID = ?", "p.ProductType = N'FINISHED_GOOD'"]
    args = [user["company_id"]]
    if search.strip():
        clauses.append("(p.SKU LIKE ? OR p.ProductName LIKE ? OR p.BarcodeValue LIKE ?)")
        args.extend([f"%{search.strip()}%"] * 3)
    if category_id is not None:
        clauses.append("p.CategoryID = ?"); args.append(category_id)
    if size:
        clauses.append("p.VariantSize = ?"); args.append(size)
    if color:
        clauses.append("p.VariantColor = ?"); args.append(color)
    if status != "ALL":
        clauses.append("p.IsActive = ?"); args.append(status == "ACTIVE")
    where = " AND ".join(clauses)
    with database_connection() as conn, database_cursor(conn) as cur:
        total = cur.execute(f"SELECT COUNT(*) FROM dbo.Products p WHERE {where}", *args).fetchone()[0]
        rows = cur.execute(f"""SELECT p.ProductID,p.SKU,p.ProductName,p.VariantDesign,p.VariantSize,
             p.VariantColor,p.SellingPrice,p.BarcodeValue,p.IsActive,p.BarcodeGeneratedAt,
             u.FullName,c.CategoryName
             FROM dbo.Products p LEFT JOIN dbo.Users u ON u.UserID=p.BarcodeGeneratedByUserID
             LEFT JOIN dbo.ProductCategories c ON c.CompanyID=p.CompanyID AND c.CategoryID=p.CategoryID
             WHERE {where} ORDER BY p.ProductName,p.ProductID OFFSET ? ROWS FETCH NEXT ? ROWS ONLY""",
             *args, offset, limit).fetchall()
    return {"items": [{"product_id":r[0],"sku":r[1],"product_name":r[2],"design":r[3],"size":r[4],
        "color":r[5],"selling_price":r[6],"barcode_value":r[7],"is_active":bool(r[8]),
        "barcode_generated_at":r[9],"barcode_generated_by":r[10],"category_name":r[11]} for r in rows],
        "total":total,"limit":limit,"offset":offset}


@router.get("/options")
def options(user=Depends(require_company_permission("inventory.barcode.manage"))):
    with database_connection() as conn, database_cursor(conn) as cur:
        cats=cur.execute("SELECT CategoryID,CategoryName FROM dbo.ProductCategories WHERE CompanyID=? ORDER BY CategoryName",user["company_id"]).fetchall()
        units=cur.execute("SELECT UnitID,UnitCode,UnitName,Symbol FROM dbo.UnitsOfMeasure WHERE IsActive=1 ORDER BY UnitName").fetchall()
        materials=cur.execute("""SELECT ProductID,SKU,ProductName,VariantDesign,VariantSize,VariantColor,UnitID
             FROM dbo.Products WHERE CompanyID=? AND ProductType=N'RAW_MATERIAL' AND IsActive=1 ORDER BY ProductName""",user["company_id"]).fetchall()
        company=cur.execute("SELECT CompanyName FROM dbo.Companies WHERE CompanyID=?",user["company_id"]).fetchone()
    return {"company_name":company[0] if company else "", "categories":[{"id":r[0],"name":r[1]} for r in cats],
        "units":[{"id":r[0],"code":r[1],"name":r[2],"symbol":r[3]} for r in units],
        "raw_materials":[{"id":r[0],"sku":r[1],"name":r[2],"design":r[3],"size":r[4],"color":r[5],"unit_id":r[6]} for r in materials],
        "buyer_sales_link_supported":False}


@router.post("/{product_id}/generate")
def generate(product_id:int, user=Depends(require_company_permission("inventory.barcode.manage"))):
    return inventory_service.generate_product_barcode(user["company_id"],product_id,user["user_id"])


@router.put("/{product_id}/materials")
def update_material_plan(product_id: int, payload: MaterialPlanUpdate,
                         user=Depends(require_company_permission("inventory.update"))):
    company_id, actor_id = user["company_id"], user["user_id"]
    ids = [part.product_id for part in payload.materials]
    if len(ids) != len(set(ids)):
        raise HTTPException(422, "A raw material can be included only once.")
    with database_connection() as conn, database_cursor(conn) as cur:
        product = cur.execute("SELECT ProductType FROM dbo.Products WHERE CompanyID=? AND ProductID=?",company_id,product_id).fetchone()
        if not product: raise HTTPException(404,"Finished good not found for this company.")
        if product[0] != "FINISHED_GOOD": raise HTTPException(422,"Material plans are only available for finished goods.")
        for part in payload.materials:
            if not cur.execute("SELECT 1 FROM dbo.Products WHERE CompanyID=? AND ProductID=? AND ProductType=N'RAW_MATERIAL' AND IsActive=1",company_id,part.product_id).fetchone():
                raise HTTPException(422,"Every component must be an active raw material in your company.")
        try:
            cur.execute("DELETE FROM dbo.FinishedGoodMaterialComponents WHERE CompanyID=? AND FinishedGoodProductID=?",company_id,product_id)
            for part in payload.materials:
                cur.execute("INSERT INTO dbo.FinishedGoodMaterialComponents(CompanyID,FinishedGoodProductID,RawMaterialProductID,QuantityPerFinishedUnit,CreatedByUserID) VALUES(?,?,?,?,?)",company_id,product_id,part.product_id,part.quantity_per_finished_unit,actor_id)
            conn.commit()
        except Exception:
            conn.rollback(); raise
    return {"product_id":product_id,"materials_saved":len(ids)}


@router.get("/{product_id}/label")
def label(product_id:int, user=Depends(require_company_permission("inventory.barcode.manage"))):
    result=inventory_service.get_product_barcode_label(user["company_id"],product_id)
    with database_connection() as conn, database_cursor(conn) as cur:
        company=cur.execute("SELECT CompanyName FROM dbo.Companies WHERE CompanyID=?",user["company_id"]).fetchone()
        audit=cur.execute("SELECT p.BarcodeGeneratedAt,u.FullName FROM dbo.Products p LEFT JOIN dbo.Users u ON u.UserID=p.BarcodeGeneratedByUserID WHERE p.CompanyID=? AND p.ProductID=?",user["company_id"],product_id).fetchone()
        materials=cur.execute("""SELECT m.ProductID,m.SKU,m.ProductName,m.VariantDesign,m.VariantSize,m.VariantColor,b.QuantityPerFinishedUnit,u.Symbol
          FROM dbo.FinishedGoodMaterialComponents b JOIN dbo.Products m ON m.CompanyID=b.CompanyID AND m.ProductID=b.RawMaterialProductID
          JOIN dbo.UnitsOfMeasure u ON u.UnitID=m.UnitID WHERE b.CompanyID=? AND b.FinishedGoodProductID=? ORDER BY m.ProductName""",user["company_id"],product_id).fetchall()
        history=[]
        if "purchasing.view" in user.get("permissions",()) and "suppliers.view" in user.get("permissions",()):
            history=cur.execute("""SELECT i.ProductID,i.SKU,i.PurchaseOrderID,po.PurchaseOrderNumber,
                po.OrderDate,po.Status,s.SupplierName,i.Quantity,i.UnitCode,i.UnitCost
                FROM dbo.PurchaseOrderItems i JOIN dbo.PurchaseOrders po
                  ON po.CompanyID=i.CompanyID AND po.PurchaseOrderID=i.PurchaseOrderID
                JOIN dbo.Suppliers s ON s.CompanyID=po.CompanyID AND s.SupplierID=po.SupplierID
                JOIN dbo.FinishedGoodMaterialComponents b ON b.CompanyID=i.CompanyID AND b.RawMaterialProductID=i.ProductID
                WHERE b.CompanyID=? AND b.FinishedGoodProductID=? AND po.CompanyID=?
                ORDER BY po.OrderDate DESC,po.PurchaseOrderID DESC""",user["company_id"],product_id,user["company_id"]).fetchall()
    result.update(company_name=company[0] if company else "",barcode_generated_at=audit[0] if audit else None,
        barcode_generated_by=audit[1] if audit else None,
        raw_materials=[{"product_id":r[0],"sku":r[1],"name":r[2],"design":r[3],"size":r[4],"color":r[5],"quantity_per_finished_unit":r[6],"unit":r[7]} for r in materials],
        purchase_history=[{"raw_material_product_id":r[0],"raw_material_sku":r[1],"purchase_order_id":r[2],"purchase_order_number":r[3],"order_date":r[4],"status":r[5],"supplier_name":r[6],"ordered_quantity":r[7],"unit":r[8],"unit_cost":r[9],"meaning":"Purchase history only; this does not establish consumption."} for r in history],
        purchase_history_supported=True,buyer_sales_link_supported=False)
    return result


@router.get("/lookup/{barcode_value}")
def lookup(barcode_value:str, user=Depends(require_company_permission("inventory.barcode.manage"))):
    product = inventory_service.lookup_product_barcode(user["company_id"],barcode_value)
    return {key: product.get(key) for key in (
        "product_id", "sku", "product_name", "product_type", "category_name",
        "unit_code", "unit_name", "variant_design", "variant_size", "variant_color",
        "selling_price", "barcode_value", "is_active",
    )}
