"""Company-scoped inventory SQL queries."""

PRODUCT_SELECT = """SELECT p.ProductID, p.SKU, p.ProductName, p.ProductType,
    p.CategoryID, c.CategoryName, p.UnitID, u.UnitCode, u.UnitName,
    p.Description, p.ReorderLevel, p.IsActive, p.CreatedAt, p.UpdatedAt,
    p.QuantityOnHand, p.VariantDesign, p.VariantSize, p.VariantColor,
    p.SellingPrice, p.BarcodeValue
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


def list_products(cursor, company_id, search, category_id, limit, offset):
    conditions = ["p.CompanyID = ?"]
    params = [company_id]
    if search:
        conditions.append("(p.SKU LIKE ? OR p.ProductName LIKE ? OR p.BarcodeValue LIKE ?)")
        params.extend([f"%{search}%", f"%{search}%", f"%{search}%"])
    if category_id is not None:
        conditions.append("p.CategoryID = ?")
        params.append(category_id)
    where = " WHERE " + " AND ".join(conditions)
    total = cursor.execute(
        f"SELECT COUNT(*) FROM dbo.Products AS p{where}", *params
    ).fetchone()[0]
    rows = cursor.execute(
        f"{PRODUCT_SELECT}{where} ORDER BY p.ProductName, p.ProductID "
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
        "quantity_on_hand": "QuantityOnHand",
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


def set_product_barcode(cursor, company_id, product_id, barcode_value):
    return cursor.execute(
        """UPDATE dbo.Products SET BarcodeValue = ?, UpdatedAt = SYSUTCDATETIME()
            WHERE CompanyID = ? AND ProductID = ?
              AND ProductType = N'FINISHED_GOOD' AND IsActive = 1
              AND SellingPrice IS NOT NULL AND BarcodeValue IS NULL""",
        barcode_value, company_id, product_id,
    )


def find_product_by_barcode(cursor, company_id, barcode_value):
    return cursor.execute(
        f"{PRODUCT_SELECT} WHERE p.CompanyID = ? AND p.BarcodeValue = ?",
        company_id, barcode_value,
    ).fetchone()
