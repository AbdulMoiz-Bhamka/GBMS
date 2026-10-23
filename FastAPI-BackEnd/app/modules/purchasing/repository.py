"""Parameterized SQL Server queries for company-scoped purchase orders."""


ORDER_COLUMNS = """po.PurchaseOrderID, po.PurchaseOrderNumber, po.SupplierID,
    s.SupplierName, po.OrderDate, po.ExpectedDeliveryDate, po.Status,
    po.Subtotal, po.TotalAmount, po.Notes, po.CreatedByUserID,
    u.FullName, po.CreatedAt, po.UpdatedAt"""


def serialize_order(row):
    return {
        "purchase_order_id": row[0], "purchase_order_number": row[1],
        "supplier_id": row[2], "supplier_name": row[3], "order_date": row[4],
        "expected_delivery_date": row[5], "status": row[6],
        "subtotal": row[7], "total_amount": row[8], "notes": row[9],
        "created_by_user_id": row[10], "created_by_name": row[11],
        "created_at": row[12], "updated_at": row[13],
    }


def get_company_order(cursor, company_id, purchase_order_id, *, lock=False):
    hint = " WITH (UPDLOCK, HOLDLOCK)" if lock else ""
    return cursor.execute(
        f"""SELECT {ORDER_COLUMNS}
            FROM dbo.PurchaseOrders AS po{hint}
            JOIN dbo.Suppliers AS s
              ON s.CompanyID = po.CompanyID AND s.SupplierID = po.SupplierID
            JOIN dbo.Users AS u ON u.UserID = po.CreatedByUserID
            WHERE po.CompanyID = ? AND po.PurchaseOrderID = ?""",
        company_id, purchase_order_id,
    ).fetchone()


def list_company_orders(cursor, company_id, search, supplier_id, order_status,
                        date_from, date_to, limit, offset):
    clauses = ["po.CompanyID = ?"]
    params = [company_id]
    if search:
        clauses.append("po.PurchaseOrderNumber LIKE ?")
        params.append(f"%{search}%")
    if supplier_id is not None:
        clauses.append("po.SupplierID = ?")
        params.append(supplier_id)
    if order_status:
        clauses.append("po.Status = ?")
        params.append(order_status)
    if date_from:
        clauses.append("po.OrderDate >= ?")
        params.append(date_from)
    if date_to:
        clauses.append("po.OrderDate <= ?")
        params.append(date_to)
    where = " WHERE " + " AND ".join(clauses)
    total = cursor.execute(
        f"SELECT COUNT_BIG(*) FROM dbo.PurchaseOrders AS po{where}", *params
    ).fetchone()[0]
    rows = cursor.execute(
        f"""SELECT {ORDER_COLUMNS}, COUNT_BIG(item.PurchaseOrderItemID) AS ItemCount
            FROM dbo.PurchaseOrders AS po
            JOIN dbo.Suppliers AS s
              ON s.CompanyID = po.CompanyID AND s.SupplierID = po.SupplierID
            JOIN dbo.Users AS u ON u.UserID = po.CreatedByUserID
            LEFT JOIN dbo.PurchaseOrderItems AS item
              ON item.CompanyID = po.CompanyID AND item.PurchaseOrderID = po.PurchaseOrderID
            {where}
            GROUP BY po.PurchaseOrderID, po.PurchaseOrderNumber, po.SupplierID,
                s.SupplierName, po.OrderDate, po.ExpectedDeliveryDate, po.Status,
                po.Subtotal, po.TotalAmount, po.Notes, po.CreatedByUserID,
                u.FullName, po.CreatedAt, po.UpdatedAt
            ORDER BY po.OrderDate DESC, po.PurchaseOrderID DESC
            OFFSET ? ROWS FETCH NEXT ? ROWS ONLY""",
        *params, offset, limit,
    ).fetchall()
    return rows, total


def supplier_is_active(cursor, company_id, supplier_id):
    return cursor.execute(
        "SELECT 1 FROM dbo.Suppliers WHERE CompanyID = ? AND SupplierID = ? AND SupplierStatus = N'ACTIVE'",
        company_id, supplier_id,
    ).fetchone()


def supplier_details(cursor, company_id, supplier_id):
    return cursor.execute(
        """SELECT SupplierName, ContactPerson, Email, Phone, Address, City,
                  Country, PaymentTerms
             FROM dbo.Suppliers WHERE CompanyID = ? AND SupplierID = ?""",
        company_id, supplier_id,
    ).fetchone()


def list_order_form_options(cursor, company_id):
    suppliers = cursor.execute(
        """SELECT SupplierID, SupplierCode, SupplierName, SupplierStatus
             FROM dbo.Suppliers WHERE CompanyID = ?
            ORDER BY SupplierName, SupplierID""",
        company_id,
    ).fetchall()
    products = cursor.execute(
        """SELECT p.ProductID, p.SKU, p.ProductName, p.ProductType,
                  p.VariantDesign, p.VariantSize, p.VariantColor, u.UnitCode
             FROM dbo.Products AS p JOIN dbo.UnitsOfMeasure AS u ON u.UnitID = p.UnitID
            WHERE p.CompanyID = ? AND p.IsActive = 1
            ORDER BY p.ProductName, p.SKU""",
        company_id,
    ).fetchall()
    return suppliers, products


def get_order_product(cursor, company_id, product_id):
    return cursor.execute(
        """SELECT p.SKU, p.ProductName, p.UnitID, u.UnitCode, p.IsActive,
                  p.CompanyID, p.VariantDesign, p.VariantSize, p.VariantColor
             FROM dbo.Products AS p JOIN dbo.UnitsOfMeasure AS u ON u.UnitID = p.UnitID
            WHERE p.CompanyID = ? AND p.ProductID = ?""",
        company_id, product_id,
    ).fetchone()


def next_order_number_value(cursor):
    return cursor.execute(
        "SELECT NEXT VALUE FOR dbo.PurchaseOrderNumberSequence"
    ).fetchone()[0]


def insert_order(cursor, *, number, company_id, supplier_id, order_date,
                 expected_delivery_date, subtotal, notes, created_by_user_id):
    return cursor.execute(
        """INSERT INTO dbo.PurchaseOrders
             (PurchaseOrderNumber, CompanyID, SupplierID, OrderDate,
              ExpectedDeliveryDate, Status, Subtotal, TotalAmount, Notes, CreatedByUserID)
           OUTPUT INSERTED.PurchaseOrderID
           VALUES (?, ?, ?, ?, ?, N'DRAFT', ?, ?, ?, ?)""",
        number, company_id, supplier_id, order_date, expected_delivery_date,
        subtotal, subtotal, notes, created_by_user_id,
    ).fetchone()[0]


def insert_order_item(cursor, *, company_id, purchase_order_id, product_id,
                      sku, product_name, unit_code, quantity, unit_cost, line_total,
                      variant_design=None, variant_size=None, variant_color=None):
    cursor.execute(
        """INSERT INTO dbo.PurchaseOrderItems
             (CompanyID, PurchaseOrderID, ProductID, SKU, ProductName,
              VariantDesign, VariantSize, VariantColor, UnitCode,
              Quantity, UnitCost, LineTotal)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        company_id, purchase_order_id, product_id, sku, product_name,
        variant_design, variant_size, variant_color, unit_code, quantity,
        unit_cost, line_total,
    )


def list_order_items(cursor, company_id, purchase_order_id):
    return cursor.execute(
        """SELECT PurchaseOrderItemID, ProductID, SKU, ProductName,
                  VariantDesign, VariantSize, VariantColor, UnitCode,
                  Quantity, UnitCost, LineTotal
             FROM dbo.PurchaseOrderItems
            WHERE CompanyID = ? AND PurchaseOrderID = ?
            ORDER BY PurchaseOrderItemID""",
        company_id, purchase_order_id,
    ).fetchall()


def replace_order_items(cursor, company_id, purchase_order_id, items):
    cursor.execute(
        "DELETE FROM dbo.PurchaseOrderItems WHERE CompanyID = ? AND PurchaseOrderID = ?",
        company_id, purchase_order_id,
    )
    for item in items:
        insert_order_item(cursor, company_id=company_id,
                          purchase_order_id=purchase_order_id, **item)


def update_draft_order(cursor, *, company_id, purchase_order_id, supplier_id,
                       order_date, expected_delivery_date, subtotal, notes):
    return cursor.execute(
        """UPDATE dbo.PurchaseOrders SET SupplierID = ?, OrderDate = ?,
                  ExpectedDeliveryDate = ?, Subtotal = ?, TotalAmount = ?,
                  Notes = ?, UpdatedAt = SYSUTCDATETIME()
            WHERE CompanyID = ? AND PurchaseOrderID = ? AND Status = N'DRAFT'""",
        supplier_id, order_date, expected_delivery_date, subtotal, subtotal,
        notes, company_id, purchase_order_id,
    )


def status_history(cursor, company_id, purchase_order_id):
    return cursor.execute(
        """SELECT h.Status, h.ChangedByUserID, u.FullName, h.Note, h.ChangedAt
             FROM dbo.PurchaseOrderStatusHistory AS h
             JOIN dbo.Users AS u ON u.UserID = h.ChangedByUserID
            WHERE h.CompanyID = ? AND h.PurchaseOrderID = ?
            ORDER BY h.PurchaseOrderStatusHistoryID""",
        company_id, purchase_order_id,
    ).fetchall()


def add_status_history(cursor, company_id, purchase_order_id, status,
                       changed_by_user_id, note=None):
    cursor.execute(
        """INSERT INTO dbo.PurchaseOrderStatusHistory
             (CompanyID, PurchaseOrderID, Status, ChangedByUserID, Note)
           VALUES (?, ?, ?, ?, ?)""",
        company_id, purchase_order_id, status, changed_by_user_id, note,
    )


def transition_order(cursor, company_id, purchase_order_id, from_status, to_status):
    return cursor.execute(
        """UPDATE dbo.PurchaseOrders SET Status = ?, UpdatedAt = SYSUTCDATETIME()
            WHERE CompanyID = ? AND PurchaseOrderID = ? AND Status = ?""",
        to_status, company_id, purchase_order_id, from_status,
    )
