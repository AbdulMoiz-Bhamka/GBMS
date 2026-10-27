"""SQL Server queries for authentication and company user management."""


def get_auth_user_by_id(cursor, user_id):
    return cursor.execute(
        """SELECT u.UserID, u.Username, u.FullName, u.Email, r.RoleName,
                  u.AccountStatus, u.CompanyID, c.CompanyStatus,
                  u.PermissionsConfigured, u.MustChangePassword, u.AuthVersion,
                  u.TemporaryPasswordExpiresAt
           FROM dbo.Users AS u
           JOIN dbo.Roles AS r ON r.RoleID = u.RoleID
           LEFT JOIN dbo.Companies AS c ON c.CompanyID = u.CompanyID
           WHERE u.UserID = ?""",
        user_id,
    ).fetchone()


def get_login_user_by_username(cursor, username):
    return cursor.execute(
        """SELECT u.UserID, u.Username, u.FullName, u.Email, r.RoleName,
                  u.AccountStatus, u.PasswordHash, u.CompanyID, c.CompanyStatus,
                  u.PermissionsConfigured, u.MustChangePassword, u.AuthVersion,
                  u.TemporaryPasswordExpiresAt
           FROM dbo.Users AS u
           JOIN dbo.Roles AS r ON r.RoleID = u.RoleID
           LEFT JOIN dbo.Companies AS c ON c.CompanyID = u.CompanyID
           WHERE u.Username = ?""",
        username,
    ).fetchone()


def list_company_users(cursor, company_id, search=""):
    conditions = ["u.CompanyID = ?"]
    params = [company_id]
    if search:
        conditions.append("(u.FullName LIKE ? OR u.Username LIKE ? OR u.Email LIKE ?)")
        params.extend([f"%{search}%"] * 3)
    where = " AND ".join(conditions)
    return cursor.execute(
        f"""SELECT u.UserID, u.Username, u.FullName, u.Email, r.RoleName,
                   u.AccountStatus, u.CreatedAt
            FROM dbo.Users AS u JOIN dbo.Roles AS r ON r.RoleID = u.RoleID
            WHERE {where} ORDER BY u.FullName, u.UserID""",
        *params,
    ).fetchall()


def get_company_user(cursor, company_id, user_id):
    return cursor.execute(
        """SELECT u.UserID, u.Username, u.FullName, u.Email, r.RoleName,
                  u.AccountStatus, u.CompanyID, u.CreatedAt, u.PermissionsConfigured
           FROM dbo.Users AS u JOIN dbo.Roles AS r ON r.RoleID = u.RoleID
           WHERE u.CompanyID = ? AND u.UserID = ?""",
        company_id,
        user_id,
    ).fetchone()


def get_password_credentials(cursor, user_id):
    return cursor.execute(
        """SELECT PasswordHash, MustChangePassword, AuthVersion
           FROM dbo.Users WITH (UPDLOCK, ROWLOCK)
           WHERE UserID = ?""",
        user_id,
    ).fetchone()


def update_own_password(cursor, user_id, auth_version, password_hash):
    return cursor.execute(
        """UPDATE dbo.Users
           SET PasswordHash = ?, MustChangePassword = 0,
               TemporaryPasswordExpiresAt = NULL,
               AuthVersion = AuthVersion + 1, UpdatedAt = SYSUTCDATETIME()
           WHERE UserID = ? AND AuthVersion = ?""",
        password_hash,
        user_id,
        auth_version,
    )


def reset_company_user_password(cursor, company_id, user_id, password_hash):
    return cursor.execute(
        """UPDATE dbo.Users
           SET PasswordHash = ?, MustChangePassword = 1,
               TemporaryPasswordExpiresAt = DATEADD(HOUR, 24, SYSUTCDATETIME()),
               AuthVersion = AuthVersion + 1, UpdatedAt = SYSUTCDATETIME()
           WHERE CompanyID = ? AND UserID = ?""",
        password_hash,
        company_id,
        user_id,
    )


def reset_super_admin_password(cursor, user_id, password_hash):
    return cursor.execute(
        """UPDATE dbo.Users
           SET PasswordHash = ?, MustChangePassword = 1,
               TemporaryPasswordExpiresAt = DATEADD(HOUR, 24, SYSUTCDATETIME()),
               AuthVersion = AuthVersion + 1, UpdatedAt = SYSUTCDATETIME()
           WHERE UserID = ? AND CompanyID IS NULL
             AND RoleID = (SELECT RoleID FROM dbo.Roles WHERE RoleName = N'SUPER_ADMIN')""",
        password_hash,
        user_id,
    )


def insert_password_audit(cursor, user_id, actor_user_id, event_type, source_ip):
    cursor.execute(
        """INSERT INTO dbo.PasswordSecurityAudit (UserID, ActorUserID, EventType, SourceIP)
           VALUES (?, ?, ?, ?)""",
        user_id,
        actor_user_id,
        event_type,
        source_ip,
    )


def list_user_permissions(cursor, user_id):
    return cursor.execute(
        """SELECT PermissionCode FROM dbo.UserPermissions
           WHERE UserID = ? ORDER BY PermissionCode""",
        user_id,
    ).fetchall()


def insert_company_user(
    cursor, payload, role_id, company_id, password_hash, permissions_configured=True
):
    identity_row = cursor.execute(
        """SET NOCOUNT ON;
           INSERT INTO dbo.Users
             (Username, FullName, Email, PasswordHash, RoleID, CompanyID, PermissionsConfigured)
           VALUES (?, ?, ?, ?, ?, ?, ?);
           SELECT CONVERT(INT, SCOPE_IDENTITY());
           SET NOCOUNT OFF;""",
        payload.username,
        payload.full_name,
        payload.email,
        password_hash,
        role_id,
        company_id,
        int(bool(permissions_configured)),
    ).fetchone()
    user_id = identity_row[0] if identity_row else None
    if user_id is None:
        raise RuntimeError("SQL Server did not return the inserted user ID.")
    return user_id


def replace_user_permissions(cursor, user_id, permission_codes, granted_by):
    cursor.execute("DELETE FROM dbo.UserPermissions WHERE UserID = ?", user_id)
    for permission_code in sorted(set(permission_codes)):
        cursor.execute(
            """INSERT INTO dbo.UserPermissions (UserID, PermissionCode, GrantedByUserID)
               VALUES (?, ?, ?)""",
            user_id,
            permission_code,
            granted_by,
        )


def update_company_user(cursor, company_id, user_id, values):
    columns = {
        "username": "Username",
        "full_name": "FullName",
        "email": "Email",
        "role_id": "RoleID",
        "permissions_configured": "PermissionsConfigured",
    }
    assignments = [f"{columns[name]} = ?" for name in values if name in columns]
    params = [values[name] for name in values if name in columns]
    assignments.append("UpdatedAt = SYSUTCDATETIME()")
    params.extend([company_id, user_id])
    return cursor.execute(
        f"UPDATE dbo.Users SET {', '.join(assignments)} WHERE CompanyID = ? AND UserID = ?",
        *params,
    )


def update_company_user_status(cursor, company_id, user_id, account_status):
    return cursor.execute(
        """UPDATE dbo.Users SET AccountStatus = ?, UpdatedAt = SYSUTCDATETIME()
           WHERE CompanyID = ? AND UserID = ?""",
        account_status,
        company_id,
        user_id,
    )


def delete_company_user(cursor, company_id, user_id):
    cursor.execute("DELETE FROM dbo.UserPermissions WHERE UserID = ?", user_id)
    cursor.execute(
        "UPDATE dbo.UserPermissions SET GrantedByUserID = NULL WHERE GrantedByUserID = ?",
        user_id,
    )
    return cursor.execute(
        "DELETE FROM dbo.Users WHERE CompanyID = ? AND UserID = ?",
        company_id,
        user_id,
    )
