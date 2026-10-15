"""SQL Server queries for account authentication and company users."""


def get_auth_user_by_id(cursor, user_id):
    return cursor.execute(
        """SELECT u.UserID, u.Username, u.FullName, u.Email, r.RoleName,
                  u.AccountStatus, u.CompanyID, c.CompanyStatus
           FROM dbo.Users AS u
           JOIN dbo.Roles AS r ON r.RoleID = u.RoleID
           LEFT JOIN dbo.Companies AS c ON c.CompanyID = u.CompanyID
           WHERE u.UserID = ?""",
        user_id,
    ).fetchone()


def get_login_user_by_username(cursor, username):
    return cursor.execute(
        """SELECT u.UserID, u.Username, u.FullName, u.Email, r.RoleName,
                  u.AccountStatus, u.PasswordHash, u.CompanyID, c.CompanyStatus
           FROM dbo.Users AS u
           JOIN dbo.Roles AS r ON r.RoleID = u.RoleID
           LEFT JOIN dbo.Companies AS c ON c.CompanyID = u.CompanyID
           WHERE u.Username = ?""",
        username,
    ).fetchone()


def list_company_users(cursor, company_id):
    return cursor.execute(
        """SELECT u.UserID, u.Username, u.FullName, u.Email, r.RoleName,
                  u.AccountStatus, u.CreatedAt
           FROM dbo.Users AS u JOIN dbo.Roles AS r ON r.RoleID = u.RoleID
           WHERE u.CompanyID = ? ORDER BY u.FullName, u.UserID""",
        company_id,
    ).fetchall()


def insert_company_user(cursor, payload, role_id, company_id, password_hash):
    identity_row = cursor.execute(
        """SET NOCOUNT ON;
           INSERT INTO dbo.Users (Username, FullName, Email, PasswordHash, RoleID, CompanyID)
           VALUES (?, ?, ?, ?, ?, ?);
           SELECT CONVERT(INT, SCOPE_IDENTITY());
           SET NOCOUNT OFF;""",
        payload.username,
        payload.full_name,
        payload.email,
        password_hash,
        role_id,
        company_id,
    ).fetchone()
    user_id = identity_row[0] if identity_row else None
    if user_id is None:
        raise RuntimeError("SQL Server did not return the inserted user ID.")
    row = cursor.execute(
        """SELECT UserID, Username, FullName, Email, AccountStatus, CreatedAt
           FROM dbo.Users WHERE UserID = ?""",
        user_id,
    ).fetchone()
    if not row:
        raise RuntimeError("The inserted company user could not be read back.")
    return row
