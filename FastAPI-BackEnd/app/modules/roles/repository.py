"""Database lookups for global GBMS roles."""


def get_role_id(cursor, role_name):
    return cursor.execute(
        "SELECT RoleID FROM dbo.Roles WHERE RoleName = ?", role_name
    ).fetchone()
