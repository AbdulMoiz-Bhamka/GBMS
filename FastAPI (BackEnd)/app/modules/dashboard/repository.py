"""SQL queries for company overview aggregates."""


def product_count(cursor, company_id):
    return cursor.execute(
        "SELECT COUNT_BIG(*) FROM dbo.Products WHERE CompanyID = ? AND IsActive = 1",
        company_id,
    ).fetchone()[0]


def inventory_chart(cursor, company_id, limit=12):
    return cursor.execute(
        """SELECT TOP (?) p.ProductID, p.ProductName, p.QuantityOnHand,
                  COALESCE(u.Symbol, u.UnitCode)
           FROM dbo.Products AS p
           JOIN dbo.UnitsOfMeasure AS u ON u.UnitID = p.UnitID
           WHERE p.CompanyID = ? AND p.IsActive = 1
           ORDER BY p.QuantityOnHand DESC, p.ProductName, p.ProductID""",
        limit,
        company_id,
    ).fetchall()


def worker_counts(cursor, company_id):
    return cursor.execute(
        """SELECT COUNT_BIG(*),
                  COALESCE(SUM(CASE WHEN u.AccountStatus = N'ACTIVE' THEN 1 ELSE 0 END), 0)
           FROM dbo.Users AS u
           JOIN dbo.Roles AS r ON r.RoleID = u.RoleID
           WHERE u.CompanyID = ? AND r.RoleName = N'WORKER'""",
        company_id,
    ).fetchone()


def snapshot_time(cursor):
    return cursor.execute("SELECT SYSUTCDATETIME()").fetchone()[0]
