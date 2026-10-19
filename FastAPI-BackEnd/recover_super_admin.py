"""Restricted local recovery for a locked-out GBMS Super Admin.

Run only on a trusted machine with access to the configured GBMS SQL Server.
This is deliberately a console script, never an HTTP endpoint.
"""

from app.core.security import generate_temporary_password, password_hasher
from app.db.connection import database_connection, database_cursor


def main():
    username = input("Super Admin username: ").strip()
    if not username:
        raise SystemExit("A username is required.")

    temporary_password = generate_temporary_password()
    password_hash = password_hasher.hash(temporary_password)
    with database_connection() as connection, database_cursor(connection) as cursor:
        target = cursor.execute(
            """SELECT u.UserID FROM dbo.Users AS u
               JOIN dbo.Roles AS r ON r.RoleID = u.RoleID
               WHERE u.Username = ? AND r.RoleName = N'SUPER_ADMIN'
                 AND u.CompanyID IS NULL""",
            username,
        ).fetchone()
        if not target:
            raise SystemExit("No matching Super Admin account was found; no changes were made.")
        user_id = target[0]
        updated = cursor.execute(
            """UPDATE dbo.Users
               SET PasswordHash = ?, MustChangePassword = 1,
                   TemporaryPasswordExpiresAt = DATEADD(HOUR, 24, SYSUTCDATETIME()),
                   AuthVersion = AuthVersion + 1, UpdatedAt = SYSUTCDATETIME()
               WHERE UserID = ?""",
            password_hash,
            user_id,
        )
        if updated.rowcount != 1:
            raise SystemExit("The account was not updated; no recovery password was issued.")
        cursor.execute(
            """INSERT INTO dbo.PasswordSecurityAudit
               (UserID, ActorUserID, EventType, SourceIP)
               VALUES (?, ?, N'PASSWORD_RESET_BY_LOCAL_RECOVERY', NULL)""",
            user_id,
            user_id,
        )
        connection.commit()

    print("Recovery completed. This temporary password is displayed once:")
    print(temporary_password)
    print("Sign in locally and change it immediately. Store and deliver it securely.")


if __name__ == "__main__":
    main()
