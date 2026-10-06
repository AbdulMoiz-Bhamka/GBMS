# seed_admin.py
from getpass import getpass

import pyodbc
from argon2 import PasswordHasher

from main import DB_NAME, DB_SERVER, DB_DRIVER, DB_USER, DB_PASSWORD


def main():
    username = input("Admin username: ").strip()
    full_name = input("Admin full name: ").strip()
    email = input("Admin email: ").strip()
    password = getpass("Admin password: ")
    if not username or not full_name or not email or len(password) < 12:
        raise SystemExit(
            "Enter all fields and use a password of at least 12 characters."
        )
    auth = (
        f"UID={DB_USER};PWD={DB_PASSWORD};"
        if DB_USER and DB_PASSWORD
        else "Trusted_Connection=yes;"
    )
    connection = pyodbc.connect(
        f"DRIVER={{{DB_DRIVER}}};SERVER={DB_SERVER};DATABASE={DB_NAME};{auth}TrustServerCertificate=yes;"
    )
    hashed = PasswordHasher().hash(password)
    with connection:
        cursor = connection.cursor()
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
            print("Super administrator created.")


if __name__ == "__main__":
    main()
