# seed_admin.py
from getpass import getpass

from app.core.security import password_hasher
from app.db.connection import database_connection, database_cursor



def main():
    username = input("Admin username: ").strip()
    full_name = input("Admin full name: ").strip()
    email = input("Admin email: ").strip()
    password = getpass("Admin password: ")
    if not username or not full_name or not email or len(password) < 12:
        raise SystemExit(
            "Enter all fields and use a password of at least 12 characters."
        )
    hashed = password_hasher.hash(password)
    with database_connection() as connection, database_cursor(connection) as cursor:
        cursor.execute("SELECT RoleID FROM dbo.Roles WHERE RoleName='SUPER_ADMIN'")
        role = cursor.fetchone()
        if not role:
            raise SystemExit("SUPER_ADMIN role is missing. Run auth_schema.sql first.")
        cursor.execute(
            """IF NOT EXISTS (SELECT 1 FROM dbo.Users WHERE Username=?)
            INSERT dbo.Users (Username, FullName, Email, PasswordHash, RoleID, AccountStatus)
            VALUES (?, ?, ?, ?, ?, 'ACTIVE')""",
            username,
            username,
            full_name,
            email,
            hashed,
            role[0],
        )
        if cursor.rowcount == 0:
            print("That username already exists; no changes were made.")
        else:
            connection.commit()
            print("Super administrator created.")


if __name__ == "__main__":
    main()
