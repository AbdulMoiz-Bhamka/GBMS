"""Company-scoped inventory SQL queries."""

PRODUCT_SELECT = """SELECT p.ProductID, p.SKU, p.ProductName, p.ProductType,
    p.CategoryID, c.CategoryName, p.UnitID, u.UnitCode, u.UnitName,
    p.Description, p.ReorderLevel, p.IsActive, p.CreatedAt, p.UpdatedAt,
    p.QuantityOnHand, p.VariantDesign, p.VariantSize, p.VariantColor,
    p.SellingPrice, p.BarcodeValue,
    CASE WHEN p.IsActive = 1 AND p.QuantityOnHand <= p.ReorderLevel THEN 1 ELSE 0 END AS IsLowStock
    FROM dbo.Products AS p
    LEFT JOIN dbo.ProductCategories AS c
      ON c.CategoryID = p.CategoryID AND c.CompanyID = p.CompanyID
    JOIN dbo.UnitsOfMeasure AS u ON u.UnitID = p.UnitID"""


def serialize_product(row):
    return {
        "product_id": row[0],
        "sku": row[1],
        "product_name": row[2],
        "product_type": row[3],
        "category_id": row[4],
        "category_name": row[5],
        "unit_id": row[6],
        "unit_code": row[7],
        "unit_name": row[8],
        "description": row[9],
        "reorder_level": row[10],
        "is_active": bool(row[11]),
        "created_at": row[12],
        "updated_at": row[13],
        "quantity_on_hand": row[14],
        "variant_design": row[15],
        "variant_size": row[16],
        "variant_color": row[17],
        "selling_price": row[18],
        "barcode_value": row[19],
        "is_low_stock": bool(row[20]) if len(row) > 20 else False,
    }


def list_categories(cursor, company_id):
    return cursor.execute(
        """SELECT CategoryID, CategoryName, Description
           FROM dbo.ProductCategories WHERE CompanyID = ? ORDER BY CategoryName""",
        company_id,
    ).fetchall()


def create_category(cursor, company_id, payload):
    return cursor.execute(
        """INSERT INTO dbo.ProductCategories (CompanyID, CategoryName, Description)
           OUTPUT INSERTED.CategoryID, INSERTED.CategoryName, INSERTED.Description
           VALUES (?, ?, ?)""",
        company_id,
        payload.category_name,
        payload.description,
    ).fetchone()


def list_units(cursor):
    return cursor.execute(
        """SELECT UnitID, UnitCode, UnitName, Symbol
           FROM dbo.UnitsOfMeasure WHERE IsActive = 1 ORDER BY UnitName"""
    ).fetchall()


def category_available(cursor, category_id, company_id):
    return cursor.execute(
        "SELECT 1 FROM dbo.ProductCategories WHERE CategoryID = ? AND CompanyID = ?",
        category_id,
        company_id,
    ).fetchone()


def active_unit_exists(cursor, unit_id):
    return cursor.execute(
        "SELECT 1 FROM dbo.UnitsOfMeasure WHERE UnitID = ? AND IsActive = 1",
        unit_id,
    ).fetchone()


def list_products(cursor, company_id, search, category_id, limit, offset, low_stock_only=False, sort_by="name", product_type=None):
    conditions = ["p.CompanyID = ?"]
    params = [company_id]
    if search:
        conditions.append("(p.SKU LIKE ? OR p.ProductName LIKE ? OR p.BarcodeValue LIKE ?)")
        params.extend([f"%{search}%", f"%{search}%", f"%{search}%"])
    if category_id is not None:
        conditions.append("p.CategoryID = ?")
        params.append(category_id)
    if product_type is not None:
        conditions.append("p.ProductType = ?")
        params.append(product_type)
    if low_stock_only:
        conditions.extend(["p.IsActive = 1", "p.QuantityOnHand <= p.ReorderLevel"])
    where = " WHERE " + " AND ".join(conditions)
    total = cursor.execute(
        f"SELECT COUNT(*) FROM dbo.Products AS p{where}", *params
    ).fetchone()[0]
    ordering = {
        "name": "p.ProductName, p.ProductID",
        "quantity": "p.QuantityOnHand ASC, p.ProductName, p.ProductID",
        "reorder_level": "p.ReorderLevel ASC, p.ProductName, p.ProductID",
    }[sort_by]
    rows = cursor.execute(
        f"{PRODUCT_SELECT}{where} ORDER BY {ordering} "
        "OFFSET ? ROWS FETCH NEXT ? ROWS ONLY",
        *params,
        offset,
        limit,
    ).fetchall()
    return rows, total


def get_company_product(cursor, company_id, product_id):
    return cursor.execute(
        f"{PRODUCT_SELECT} WHERE p.CompanyID = ? AND p.ProductID = ?",
        company_id,
        product_id,
    ).fetchone()


def insert_product(cursor, company_id, payload):
    return cursor.execute(
        """INSERT INTO dbo.Products
           (CompanyID, CategoryID, SKU, ProductName, ProductType, UnitID,
            Description, ReorderLevel, QuantityOnHand, VariantDesign,
            VariantSize, VariantColor, SellingPrice)
           OUTPUT INSERTED.ProductID
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        company_id,
        payload.category_id,
        payload.sku,
        payload.product_name,
        payload.product_type,
        payload.unit_id,
        payload.description,
        payload.reorder_level,
        payload.quantity_on_hand,
        payload.variant_design,
        payload.variant_size,
        payload.variant_color,
        payload.selling_price,
    ).fetchone()[0]


def update_product(cursor, company_id, product_id, values):
    columns = {
        "sku": "SKU",
        "product_name": "ProductName",
        "product_type": "ProductType",
        "unit_id": "UnitID",
        "category_id": "CategoryID",
        "description": "Description",
        "reorder_level": "ReorderLevel",
        "variant_design": "VariantDesign",
        "variant_size": "VariantSize",
        "variant_color": "VariantColor",
        "selling_price": "SellingPrice",
    }
    assignments = [f"{columns[name]} = ?" for name in values]
    params = list(values.values())
    assignments.append("UpdatedAt = SYSUTCDATETIME()")
    params.extend([company_id, product_id])
    return cursor.execute(
        f"UPDATE dbo.Products SET {', '.join(assignments)} "
        "WHERE CompanyID = ? AND ProductID = ?",
        *params,
    )


def get_product_stock_for_update(cursor, company_id, product_id):
    return cursor.execute(
        """SELECT ProductID, ProductType, UnitID, QuantityOnHand, ReorderLevel, IsActive
             FROM dbo.Products WITH (UPDLOCK, ROWLOCK)
            WHERE CompanyID = ? AND ProductID = ?""",
        company_id, product_id,
    ).fetchone()


def get_idempotent_transaction(cursor, company_id, idempotency_key):
    return cursor.execute(
        """SELECT InventoryTransactionID, CompanyID, ProductID, TransactionType,
                  QuantityChanged, PreviousBalance, NewBalance, SupplierID, PurchaseOrderID,
                  ReferenceNumber, CreatedByUserID, TransactionAt, Notes
             FROM dbo.InventoryTransactions WITH (UPDLOCK, HOLDLOCK)
            WHERE CompanyID = ? AND IdempotencyKey = ?""",
        company_id, str(idempotency_key),
    ).fetchone()


def supplier_is_active(cursor, company_id, supplier_id):
    return cursor.execute(
        "SELECT 1 FROM dbo.Suppliers WHERE CompanyID = ? AND SupplierID = ? AND SupplierStatus = N'ACTIVE'",
        company_id, supplier_id,
    ).fetchone()


def supplier_belongs_to_company(cursor, company_id, supplier_id):
    return cursor.execute(
        "SELECT 1 FROM dbo.Suppliers WHERE CompanyID = ? AND SupplierID = ?",
        company_id, supplier_id,
    ).fetchone()


def get_receipt_purchase_order(cursor, company_id, purchase_order_id, product_id):
    return cursor.execute(
        """SELECT po.SupplierID, po.Status
             FROM dbo.PurchaseOrders po
            WHERE po.CompanyID = ? AND po.PurchaseOrderID = ?
              AND EXISTS (
                  SELECT 1 FROM dbo.PurchaseOrderItems i
                   WHERE i.CompanyID = po.CompanyID AND i.PurchaseOrderID = po.PurchaseOrderID
                     AND i.ProductID = ?
              )""",
        company_id, purchase_order_id, product_id,
    ).fetchone()


def update_stock_balance(cursor, company_id, product_id, previous_balance, new_balance):
    return cursor.execute(
        """UPDATE dbo.Products SET QuantityOnHand = ?, UpdatedAt = SYSUTCDATETIME()
            WHERE CompanyID = ? AND ProductID = ? AND QuantityOnHand = ?""",
        new_balance, company_id, product_id, previous_balance,
    )


def insert_inventory_transaction(cursor, *, company_id, product_id, transaction_type,
                                 quantity_changed, previous_balance, new_balance,
                                 supplier_id, purchase_order_id, reference_number,
                                 created_by_user_id, notes, idempotency_key,
                                 material_lot_id=None, goods_receipt_id=None,
                                 production_batch_id=None):
    return cursor.execute(
        """INSERT INTO dbo.InventoryTransactions
             (CompanyID, ProductID, TransactionType, QuantityChanged, PreviousBalance,
              NewBalance, SupplierID, PurchaseOrderID, ReferenceNumber,
              CreatedByUserID, Notes, IdempotencyKey, MaterialLotID,
              GoodsReceiptID, ProductionBatchID)
           OUTPUT INSERTED.InventoryTransactionID, INSERTED.CompanyID, INSERTED.ProductID,
                  INSERTED.TransactionType, INSERTED.QuantityChanged, INSERTED.PreviousBalance,
                  INSERTED.NewBalance, INSERTED.SupplierID, INSERTED.PurchaseOrderID,
                  INSERTED.ReferenceNumber, INSERTED.CreatedByUserID, INSERTED.TransactionAt,
                  INSERTED.Notes
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        company_id, product_id, transaction_type, quantity_changed, previous_balance,
        new_balance, supplier_id, purchase_order_id, reference_number,
        created_by_user_id, notes, str(idempotency_key), material_lot_id,
        goods_receipt_id, production_batch_id,
    ).fetchone()


def list_stock_transactions(cursor, company_id, product_id, transaction_type,
                            date_from, date_to, limit, offset):
    conditions = ["t.CompanyID = ?", "t.ProductID = ?"]
    params = [company_id, product_id]
    if transaction_type:
        conditions.append("t.TransactionType = ?"); params.append(transaction_type)
    if date_from:
        conditions.append("t.TransactionAt >= ?"); params.append(date_from)
    if date_to:
        conditions.append("t.TransactionAt < DATEADD(day, 1, ?)"); params.append(date_to)
    where = " AND ".join(conditions)
    total = cursor.execute(
        f"SELECT COUNT_BIG(*) FROM dbo.InventoryTransactions t WHERE {where}", *params
    ).fetchone()[0]
    rows = cursor.execute(
        f"""SELECT t.InventoryTransactionID,t.TransactionType,t.QuantityChanged,
                  t.PreviousBalance,t.NewBalance,t.SupplierID,s.SupplierName,
                  t.PurchaseOrderID,po.PurchaseOrderNumber,t.ReferenceNumber,
                  t.CreatedByUserID,u.FullName,t.TransactionAt,t.Notes
             FROM dbo.InventoryTransactions t
             LEFT JOIN dbo.Suppliers s ON s.CompanyID=t.CompanyID AND s.SupplierID=t.SupplierID
             LEFT JOIN dbo.PurchaseOrders po ON po.CompanyID=t.CompanyID AND po.PurchaseOrderID=t.PurchaseOrderID
             LEFT JOIN dbo.Users u ON u.UserID=t.CreatedByUserID
            WHERE {where}
            ORDER BY t.TransactionAt DESC,t.InventoryTransactionID DESC
            OFFSET ? ROWS FETCH NEXT ? ROWS ONLY""",
        *params, offset, limit,
    ).fetchall()
    return rows, total


def count_low_stock(cursor, company_id):
    return cursor.execute(
        """SELECT COUNT_BIG(*) FROM dbo.Products
            WHERE CompanyID = ? AND IsActive = 1 AND QuantityOnHand <= ReorderLevel""",
        company_id,
    ).fetchone()[0]


def update_product_status(cursor, company_id, product_id, is_active):
    return cursor.execute(
        """UPDATE dbo.Products SET IsActive = ?, UpdatedAt = SYSUTCDATETIME()
           WHERE CompanyID = ? AND ProductID = ?""",
        is_active,
        company_id,
        product_id,
    )


def get_barcode_product(cursor, company_id, product_id):
    return cursor.execute(
        """SELECT p.ProductID, p.SKU, p.ProductName, p.ProductType,
                  p.VariantDesign, p.VariantSize, p.VariantColor,
                  p.SellingPrice, p.BarcodeValue, p.IsActive
             FROM dbo.Products AS p
            WHERE p.CompanyID = ? AND p.ProductID = ?""",
        company_id, product_id,
    ).fetchone()


def set_product_barcode(cursor, company_id, product_id, barcode_value, user_id):
    return cursor.execute(
        """UPDATE dbo.Products SET BarcodeValue = ?, BarcodeGeneratedAt = SYSUTCDATETIME(),
                  BarcodeGeneratedByUserID = ?, UpdatedAt = SYSUTCDATETIME()
            WHERE CompanyID = ? AND ProductID = ?
              AND ProductType = N'FINISHED_GOOD' AND IsActive = 1
              AND SellingPrice IS NOT NULL AND BarcodeValue IS NULL""",
        barcode_value, user_id, company_id, product_id,
    )


def find_product_by_barcode(cursor, company_id, barcode_value):
    return cursor.execute(
        f"{PRODUCT_SELECT} WHERE p.CompanyID = ? AND p.BarcodeValue = ?",
        company_id, barcode_value,
    ).fetchone()
