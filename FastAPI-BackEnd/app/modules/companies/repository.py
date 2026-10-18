"""SQL Server queries for platform-managed companies."""

COMPANY_COLUMNS = (
    "CompanyID, CompanyName, CompanyCode, Email, Phone, Address, "
    "CompanyStatus, CreatedAt, UpdatedAt"
)


def serialize_company(row):
    return {
        "company_id": row[0],
        "company_name": row[1],
        "company_code": row[2],
        "email": row[3],
        "phone": row[4],
        "address": row[5],
        "company_status": row[6],
        "created_at": row[7],
        "updated_at": row[8],
    }


def list_companies(cursor, search, limit, offset):
    where = "WHERE CompanyName LIKE ? OR CompanyCode LIKE ? OR Email LIKE ?" if search else ""
    search_params = [f"%{search}%"] * 3 if search else []
    total = cursor.execute(
        f"SELECT COUNT(*) FROM dbo.Companies {where}", *search_params
    ).fetchone()[0]
    rows = cursor.execute(
        f"SELECT {COMPANY_COLUMNS} FROM dbo.Companies {where} "
        "ORDER BY CompanyName, CompanyID OFFSET ? ROWS FETCH NEXT ? ROWS ONLY",
        *search_params,
        offset,
        limit,
    ).fetchall()
    return rows, total


def create_company(cursor, payload):
    return cursor.execute(
        """INSERT INTO dbo.Companies (CompanyName, CompanyCode, Email, Phone, Address)
           OUTPUT INSERTED.CompanyID, INSERTED.CompanyName, INSERTED.CompanyCode,
                  INSERTED.Email, INSERTED.Phone, INSERTED.Address,
                  INSERTED.CompanyStatus, INSERTED.CreatedAt, INSERTED.UpdatedAt
           VALUES (?, ?, ?, ?, ?)""",
        payload.company_name,
        payload.company_code,
        payload.email,
        payload.phone,
        payload.address,
    ).fetchone()


def get_company(cursor, company_id):
    return cursor.execute(
        f"SELECT {COMPANY_COLUMNS} FROM dbo.Companies WHERE CompanyID = ?",
        company_id,
    ).fetchone()


def update_company(cursor, company_id, values):
    columns = {
        "company_name": "CompanyName",
        "company_code": "CompanyCode",
        "email": "Email",
        "phone": "Phone",
        "address": "Address",
    }
    assignments = [f"{columns[name]} = ?" for name in values]
    parameters = list(values.values())
    assignments.append("UpdatedAt = SYSUTCDATETIME()")
    parameters.append(company_id)
    return cursor.execute(
        f"""UPDATE dbo.Companies SET {', '.join(assignments)}
            OUTPUT INSERTED.CompanyID, INSERTED.CompanyName, INSERTED.CompanyCode,
                   INSERTED.Email, INSERTED.Phone, INSERTED.Address,
                   INSERTED.CompanyStatus, INSERTED.CreatedAt, INSERTED.UpdatedAt
            WHERE CompanyID = ?""",
        *parameters,
    ).fetchone()


def update_company_status(cursor, company_id, company_status):
    return cursor.execute(
        f"""UPDATE dbo.Companies SET CompanyStatus = ?, UpdatedAt = SYSUTCDATETIME()
            OUTPUT INSERTED.CompanyID, INSERTED.CompanyName, INSERTED.CompanyCode,
                   INSERTED.Email, INSERTED.Phone, INSERTED.Address,
                   INSERTED.CompanyStatus, INSERTED.CreatedAt, INSERTED.UpdatedAt
            WHERE CompanyID = ?""",
        company_status,
        company_id,
    ).fetchone()
