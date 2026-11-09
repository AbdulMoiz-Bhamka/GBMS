"""Parameterized SQL for receiving PO quantities into company-owned material lots."""


def list_open_orders(cursor, company_id):
    return cursor.execute(
        """SELECT po.PurchaseOrderID,po.PurchaseOrderNumber,s.SupplierID,s.SupplierName,po.Status,po.OrderDate,
                  COUNT_BIG(i.PurchaseOrderItemID)
             FROM dbo.PurchaseOrders po
             JOIN dbo.Suppliers s ON s.CompanyID=po.CompanyID AND s.SupplierID=po.SupplierID
             JOIN dbo.PurchaseOrderItems i ON i.CompanyID=po.CompanyID AND i.PurchaseOrderID=po.PurchaseOrderID
            WHERE po.CompanyID=? AND po.Status IN (N'SUBMITTED',N'PARTIALLY_RECEIVED')
            GROUP BY po.PurchaseOrderID,po.PurchaseOrderNumber,s.SupplierID,s.SupplierName,po.Status,po.OrderDate
            ORDER BY po.OrderDate DESC,po.PurchaseOrderID DESC""", company_id
    ).fetchall()


def list_order_lines(cursor, company_id, purchase_order_id):
    return cursor.execute(
        """SELECT i.PurchaseOrderItemID,i.ProductID,i.SKU,i.ProductName,i.VariantDesign,i.VariantSize,
                  i.VariantColor,i.UnitCode,i.Quantity,i.UnitCost,p.ProductType,
                  COALESCE((SELECT SUM(r.ReceivedQuantity) FROM dbo.GoodsReceiptItems r
                             WHERE r.CompanyID=i.CompanyID AND r.PurchaseOrderItemID=i.PurchaseOrderItemID),0)
             FROM dbo.PurchaseOrderItems i
             JOIN dbo.Products p ON p.CompanyID=i.CompanyID AND p.ProductID=i.ProductID
            WHERE i.CompanyID=? AND i.PurchaseOrderID=?
            ORDER BY i.PurchaseOrderItemID""", company_id, purchase_order_id
    ).fetchall()


def get_order_for_update(cursor, company_id, purchase_order_id):
    return cursor.execute(
        """SELECT po.SupplierID,po.Status,po.PurchaseOrderNumber
             FROM dbo.PurchaseOrders po WITH (UPDLOCK,HOLDLOCK)
            WHERE po.CompanyID=? AND po.PurchaseOrderID=?""", company_id, purchase_order_id
    ).fetchone()


def get_receipt_by_key(cursor, company_id, idempotency_key):
    return cursor.execute(
        "SELECT GoodsReceiptID,ReceiptNumber FROM dbo.GoodsReceipts WHERE CompanyID=? AND IdempotencyKey=?",
        company_id, str(idempotency_key)
    ).fetchone()


def create_receipt(cursor, company_id, receipt_number, supplier_id, purchase_order_id,
                   actor_id, notes, idempotency_key):
    return cursor.execute(
        """INSERT INTO dbo.GoodsReceipts(CompanyID,ReceiptNumber,SupplierID,PurchaseOrderID,CreatedByUserID,Notes,IdempotencyKey)
           OUTPUT INSERTED.GoodsReceiptID VALUES(?,?,?,?,?,?,?)""",
        company_id, receipt_number, supplier_id, purchase_order_id, actor_id, notes, str(idempotency_key)
    ).fetchone()[0]


def create_lot(cursor, company_id, product_id, receipt_id, lot_number, quantity):
    return cursor.execute(
        """INSERT INTO dbo.MaterialLots(CompanyID,ProductID,GoodsReceiptID,LotNumber,OriginalQuantity,RemainingQuantity)
           OUTPUT INSERTED.MaterialLotID VALUES(?,?,?,?,?,?)""",
        company_id, product_id, receipt_id, lot_number, quantity, quantity
    ).fetchone()[0]


def create_receipt_item(cursor, company_id, receipt_id, purchase_order_id,
                        product_id, po_item_id, lot_id, quantity, unit_cost):
    return cursor.execute(
        """INSERT INTO dbo.GoodsReceiptItems(CompanyID,GoodsReceiptID,PurchaseOrderID,ProductID,
                  PurchaseOrderItemID,MaterialLotID,ReceivedQuantity,UnitCost)
           VALUES(?,?,?,?,?,?,?,?)""",
        company_id, receipt_id, purchase_order_id, product_id, po_item_id, lot_id, quantity, unit_cost
    )


def get_product_for_update(cursor, company_id, product_id):
    return cursor.execute(
        """SELECT ProductType,QuantityOnHand,IsActive
             FROM dbo.Products WITH (UPDLOCK,ROWLOCK)
            WHERE CompanyID=? AND ProductID=?""", company_id, product_id
    ).fetchone()


def get_order_line(cursor, company_id, purchase_order_id, po_item_id):
    return cursor.execute(
        """SELECT ProductID,Quantity,UnitCost FROM dbo.PurchaseOrderItems WITH (UPDLOCK,HOLDLOCK)
            WHERE CompanyID=? AND PurchaseOrderID=? AND PurchaseOrderItemID=?""",
        company_id, purchase_order_id, po_item_id
    ).fetchone()


def received_for_line(cursor, company_id, po_item_id):
    return cursor.execute(
        "SELECT COALESCE(SUM(ReceivedQuantity),0) FROM dbo.GoodsReceiptItems WHERE CompanyID=? AND PurchaseOrderItemID=?",
        company_id, po_item_id
    ).fetchone()[0]


def receipt_details(cursor, company_id, receipt_id):
    header = cursor.execute(
        """SELECT r.GoodsReceiptID,r.ReceiptNumber,r.SupplierID,s.SupplierName,r.PurchaseOrderID,
                  po.PurchaseOrderNumber,r.ReceivedAt,r.CreatedByUserID,u.FullName,r.Notes
             FROM dbo.GoodsReceipts r
             JOIN dbo.Suppliers s ON s.CompanyID=r.CompanyID AND s.SupplierID=r.SupplierID
             JOIN dbo.PurchaseOrders po ON po.CompanyID=r.CompanyID AND po.PurchaseOrderID=r.PurchaseOrderID
             JOIN dbo.Users u ON u.UserID=r.CreatedByUserID
            WHERE r.CompanyID=? AND r.GoodsReceiptID=?""", company_id, receipt_id
    ).fetchone()
    if not header:
        return None, []
    lines = cursor.execute(
        """SELECT i.GoodsReceiptItemID,i.ProductID,p.SKU,p.ProductName,i.PurchaseOrderItemID,
                  i.MaterialLotID,l.LotNumber,i.ReceivedQuantity,u.UnitCode,i.UnitCost
             FROM dbo.GoodsReceiptItems i
             JOIN dbo.Products p ON p.CompanyID=i.CompanyID AND p.ProductID=i.ProductID
             JOIN dbo.MaterialLots l ON l.CompanyID=i.CompanyID AND l.MaterialLotID=i.MaterialLotID
             JOIN dbo.UnitsOfMeasure u ON u.UnitID=p.UnitID
            WHERE i.CompanyID=? AND i.GoodsReceiptID=? ORDER BY i.GoodsReceiptItemID""",
        company_id, receipt_id
    ).fetchall()
    return header, lines


def list_lots(cursor, company_id, product_id=None):
    where = "l.CompanyID=?"
    args = [company_id]
    if product_id is not None:
        where += " AND l.ProductID=?"
        args.append(product_id)
    return cursor.execute(
        f"""SELECT l.MaterialLotID,l.ProductID,p.SKU,p.ProductName,l.GoodsReceiptID,r.ReceiptNumber,
                   r.PurchaseOrderID,po.PurchaseOrderNumber,r.SupplierID,s.SupplierName,l.LotNumber,
                   l.OriginalQuantity,l.RemainingQuantity,u.UnitCode,l.CreatedAt
              FROM dbo.MaterialLots l
              JOIN dbo.Products p ON p.CompanyID=l.CompanyID AND p.ProductID=l.ProductID
              JOIN dbo.GoodsReceipts r ON r.CompanyID=l.CompanyID AND r.GoodsReceiptID=l.GoodsReceiptID
              JOIN dbo.PurchaseOrders po ON po.CompanyID=r.CompanyID AND po.PurchaseOrderID=r.PurchaseOrderID
              JOIN dbo.Suppliers s ON s.CompanyID=r.CompanyID AND s.SupplierID=r.SupplierID
              JOIN dbo.UnitsOfMeasure u ON u.UnitID=p.UnitID
             WHERE {where} ORDER BY l.CreatedAt DESC,l.MaterialLotID DESC""", *args
    ).fetchall()


def insert_barcode(cursor, company_id, barcode_value, lot_id, actor_id):
    return cursor.execute(
        """INSERT INTO dbo.BarcodeRegistry(CompanyID,BarcodeValue,EntityType,MaterialLotID,CreatedByUserID)
           VALUES(?, ?, N'MATERIAL_LOT', ?, ?)""", company_id, barcode_value, lot_id, actor_id
    )


def get_barcode_entity(cursor, company_id, barcode_value):
    return cursor.execute(
        """SELECT EntityType,ProductID,MaterialLotID,ProductionBatchID,BundleID
             FROM dbo.BarcodeRegistry WHERE CompanyID=? AND BarcodeValue=?""",
        company_id, barcode_value
    ).fetchone()


def get_lot_barcode_record(cursor, company_id, lot_id):
    return cursor.execute(
        """SELECT b.BarcodeValue,l.MaterialLotID,l.LotNumber,l.ProductID,p.SKU,p.ProductName,
                  s.SupplierName,po.PurchaseOrderNumber,r.ReceiptNumber,l.OriginalQuantity,
                  l.RemainingQuantity,u.UnitCode,c.CompanyName
             FROM dbo.BarcodeRegistry b
             JOIN dbo.MaterialLots l ON l.CompanyID=b.CompanyID AND l.MaterialLotID=b.MaterialLotID
             JOIN dbo.Products p ON p.CompanyID=l.CompanyID AND p.ProductID=l.ProductID
             JOIN dbo.GoodsReceipts r ON r.CompanyID=l.CompanyID AND r.GoodsReceiptID=l.GoodsReceiptID
             JOIN dbo.Suppliers s ON s.CompanyID=r.CompanyID AND s.SupplierID=r.SupplierID
             JOIN dbo.PurchaseOrders po ON po.CompanyID=r.CompanyID AND po.PurchaseOrderID=r.PurchaseOrderID
             JOIN dbo.UnitsOfMeasure u ON u.UnitID=p.UnitID
             JOIN dbo.Companies c ON c.CompanyID=l.CompanyID
            WHERE b.CompanyID=? AND b.EntityType=N'MATERIAL_LOT' AND l.MaterialLotID=?""",
        company_id, lot_id
    ).fetchone()
