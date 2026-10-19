"""Parameterized SQL Server queries for company-owned suppliers."""

SUPPLIER_COLUMNS = (
    "SupplierID, SupplierCode, SupplierName, ContactPerson, Email, Phone, "
    "AlternatePhone, Address, City, Country, TaxRegistrationNumber, "
    "PaymentTerms, Notes, SupplierStatus, CreatedAt, UpdatedAt"
)


def serialize_supplier(row):
    return {
        "supplier_id": row[0],
        "supplier_code": row[1],
        "supplier_name": row[2],
        "contact_person": row[3],
        "email": row[4],
        "phone": row[5],
        "alternate_phone": row[6],
        "address": row[7],
        "city": row[8],
        "country": row[9],
        "tax_registration_number": row[10],
        "payment_terms": row[11],
        "notes": row[12],
        "supplier_status": row[13],
        "created_at": row[14],
        "updated_at": row[15],
    }


def list_suppliers(cursor, company_id, search, supplier_status, limit, offset):
    conditions = ["CompanyID = ?"]
    params = [company_id]
    if search:
        conditions.append(
            "(SupplierCode LIKE ? OR SupplierName LIKE ? OR ContactPerson LIKE ? OR Phone LIKE ? OR Email LIKE ?)"
        )
        params.extend([f"%{search}%"] * 5)
    if supplier_status:
        conditions.append("SupplierStatus = ?")
        params.append(supplier_status)
    where = " WHERE " + " AND ".join(conditions)
    total = cursor.execute(
        f"SELECT COUNT(*) FROM dbo.Suppliers{where}", *params
    ).fetchone()[0]
    rows = cursor.execute(
        f"SELECT {SUPPLIER_COLUMNS} FROM dbo.Suppliers{where} "
        "ORDER BY SupplierName, SupplierID OFFSET ? ROWS FETCH NEXT ? ROWS ONLY",
        *params,
        offset,
        limit,
    ).fetchall()
    return rows, total


def get_supplier(cursor, company_id, supplier_id):
    return cursor.execute(
        f"SELECT {SUPPLIER_COLUMNS} FROM dbo.Suppliers WHERE CompanyID = ? AND SupplierID = ?",
        company_id,
        supplier_id,
    ).fetchone()


def insert_supplier(cursor, company_id, payload):
    return cursor.execute(
        """INSERT INTO dbo.Suppliers
           (CompanyID, SupplierCode, SupplierName, ContactPerson, Email, Phone,
            AlternatePhone, Address, City, Country, TaxRegistrationNumber,
            PaymentTerms, Notes)
           OUTPUT INSERTED.SupplierID
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        company_id,
        payload.supplier_code,
        payload.supplier_name,
        payload.contact_person,
        payload.email,
        payload.phone,
        payload.alternate_phone,
        payload.address,
        payload.city,
        payload.country,
        payload.tax_registration_number,
        payload.payment_terms,
        payload.notes,
    ).fetchone()[0]


def update_supplier(cursor, company_id, supplier_id, values):
    columns = {
        "supplier_code": "SupplierCode",
        "supplier_name": "SupplierName",
        "contact_person": "ContactPerson",
        "email": "Email",
        "phone": "Phone",
        "alternate_phone": "AlternatePhone",
        "address": "Address",
        "city": "City",
        "country": "Country",
        "tax_registration_number": "TaxRegistrationNumber",
        "payment_terms": "PaymentTerms",
        "notes": "Notes",
    }
    assignments = [f"{columns[name]} = ?" for name in values]
    params = list(values.values())
    assignments.append("UpdatedAt = SYSUTCDATETIME()")
    params.extend([company_id, supplier_id])
    return cursor.execute(
        f"UPDATE dbo.Suppliers SET {', '.join(assignments)} "
        "WHERE CompanyID = ? AND SupplierID = ?",
        *params,
    )


def update_supplier_status(cursor, company_id, supplier_id, supplier_status):
    return cursor.execute(
        """UPDATE dbo.Suppliers SET SupplierStatus = ?, UpdatedAt = SYSUTCDATETIME()
           WHERE CompanyID = ? AND SupplierID = ?""",
        supplier_status,
        company_id,
        supplier_id,
    )
