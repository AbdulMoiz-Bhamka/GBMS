# test_company_inventory.py
"""Focused, database-free checks for tenant authorization and request schemas."""

import unittest
from unittest.mock import patch

from fastapi import HTTPException
from pydantic import ValidationError

import main
from main import (
    CompanyCreate,
    CompanyUserCreate,
    allowed_origins,
    ProductCreate,
    create_company_user,
    ensure_category_for_company,
    require_company_user,
    require_super_admin,
    validate_role_company,
)


class FakeCategoryCursor:
    def __init__(self, found):
        self.found = found
        self.sql = None
        self.params = None

    def execute(self, sql, *params):
        self.sql = sql
        self.params = params
        return self

    def fetchone(self):
        return (1,) if self.found else None


class FakeUserCursor:
    def __init__(self, *, company_status="ACTIVE", role_id=2, insert_error=None):
        self.company_status = company_status
        self.role_id = role_id
        self.insert_error = insert_error
        self.result = None
        self.insert_sql = None
        self.insert_params = None

    def execute(self, sql, *params):
        normalized = " ".join(sql.split())
        if "SELECT CompanyStatus FROM dbo.Companies" in normalized:
            self.result = (self.company_status,) if self.company_status else None
        elif "SELECT RoleID FROM dbo.Roles" in normalized:
            self.result = (self.role_id,) if self.role_id else None
        elif "INSERT INTO dbo.Users" in normalized:
            self.insert_sql = normalized
            self.insert_params = params
            if self.insert_error:
                raise self.insert_error
            if "SCOPE_IDENTITY()" not in normalized:
                raise AssertionError("SCOPE_IDENTITY must run in the INSERT batch.")
            self.result = (77,)
        elif "FROM dbo.Users WHERE UserID = ?" in normalized:
            self.result = (77, "aman365", "Aman", "aman@example.com", "ACTIVE", "2026-10-13")
        else:
            raise AssertionError(f"Unexpected SQL in fake cursor: {normalized}")
        return self

    def fetchone(self):
        return self.result

    def close(self):
        pass


class FakeUserConnection:
    def __init__(self, cursor):
        self.fake_cursor = cursor
        self.committed = False
        self.rolled_back = False
        self.closed = False

    def cursor(self):
        return self.fake_cursor

    def commit(self):
        self.committed = True

    def rollback(self):
        self.rolled_back = True

    def close(self):
        self.closed = True


class CompanyInventoryValidationTests(unittest.TestCase):
    def test_local_frontend_origins_are_always_allowed(self):
        self.assertIn("http://localhost:5173", allowed_origins)
        self.assertIn("http://127.0.0.1:5173", allowed_origins)

    def test_super_admin_must_have_no_company(self):
        validate_role_company("SUPER_ADMIN", None, None)
        with self.assertRaises(HTTPException) as error:
            validate_role_company("SUPER_ADMIN", 10, "ACTIVE")
        self.assertEqual(error.exception.status_code, 403)

    def test_company_roles_require_an_active_company(self):
        validate_role_company("COMPANY_ADMIN", 10, "ACTIVE")
        with self.assertRaises(HTTPException) as unassigned:
            validate_role_company("INVENTORY_USER", None, None)
        self.assertEqual(unassigned.exception.status_code, 403)
        with self.assertRaises(HTTPException) as inactive:
            validate_role_company("COMPANY_ADMIN", 10, "INACTIVE")
        self.assertEqual(inactive.exception.status_code, 403)

    def test_inventory_access_is_not_granted_to_platform_or_unlisted_roles(self):
        with self.assertRaises(HTTPException) as platform_user:
            require_company_user({"role_name": "SUPER_ADMIN", "company_id": None})
        self.assertEqual(platform_user.exception.status_code, 403)
        with self.assertRaises(HTTPException) as unlisted_role:
            require_company_user({"role_name": "HR_USER", "company_id": 12})
        self.assertEqual(unlisted_role.exception.status_code, 403)

    def test_category_lookup_is_scoped_to_company(self):
        cursor = FakeCategoryCursor(found=True)
        ensure_category_for_company(cursor, 4, 12)
        self.assertIn("CategoryID = ? AND CompanyID = ?", cursor.sql)
        self.assertEqual(cursor.params, (4, 12))

    def test_missing_cross_company_category_is_rejected(self):
        with self.assertRaises(HTTPException) as error:
            ensure_category_for_company(FakeCategoryCursor(found=False), 4, 12)
        self.assertEqual(error.exception.status_code, 422)

    def test_company_code_is_normalized(self):
        company = CompanyCreate(company_name="Northstar Apparel", company_code="north-01")
        self.assertEqual(company.company_code, "NORTH-01")

    def test_company_user_requires_strong_password_and_company_role(self):
        valid = {
            "username": "moiz_admin",
            "full_name": "Moiz Admin",
            "email": "admin@example.com",
            "password": "a-long-password-123",
        }
        self.assertEqual(CompanyUserCreate(**valid).role_name, "COMPANY_ADMIN")
        with self.assertRaises(ValidationError):
            CompanyUserCreate(**{**valid, "password": "short"})
        with self.assertRaises(ValidationError):
            CompanyUserCreate(**{**valid, "role_name": "SUPER_ADMIN"})
        with self.assertRaises(ValidationError):
            CompanyUserCreate(**{**valid, "company_id": 99})
        self.assertEqual(CompanyUserCreate(**valid).username, "moiz_admin")
        with self.assertRaises(ValidationError):
            CompanyUserCreate(**{**valid, "username": "bad name"})

    def test_company_code_pattern_rejects_invalid_characters(self):
        with self.assertRaises(ValidationError):
            CompanyCreate(company_name="Northstar", company_code="bad code")

    @staticmethod
    def company_user_payload():
        return CompanyUserCreate(
            username="aman365",
            full_name="Aman",
            email="aman@example.com",
            password="a-secure-test-password",
        )

    def call_create_company_user(self, cursor, company_id=1):
        connection = FakeUserConnection(cursor)
        with patch("main.get_connection", return_value=connection):
            response = create_company_user(
                self.company_user_payload(), company_id, {"role_name": "SUPER_ADMIN"}
            )
        return response, connection

    def test_company_user_creation_uses_trigger_compatible_insert_and_hashes_password(self):
        cursor = FakeUserCursor()
        response, connection = self.call_create_company_user(cursor)
        self.assertEqual(response["user_id"], 77)
        self.assertNotIn("password", response)
        self.assertNotIn("PasswordHash", response)
        self.assertNotIn("OUTPUT", cursor.insert_sql.upper())
        self.assertIn("SCOPE_IDENTITY()", cursor.insert_sql)
        self.assertTrue(cursor.insert_params[3].startswith("$argon2"))
        self.assertNotEqual(cursor.insert_params[3], "a-secure-test-password")
        self.assertEqual(cursor.insert_params[-1], 1)
        self.assertTrue(connection.committed)
        self.assertFalse(connection.rolled_back)

    def test_company_user_duplicate_username_and_email_return_conflict(self):
        for constraint, expected in (
            ("UQ_Users_Username", "username"),
            ("UQ_Users_Email", "email"),
        ):
            cursor = FakeUserCursor(
                insert_error=main.pyodbc.IntegrityError(
                    f"2627 duplicate key in {constraint}"
                )
            )
            connection = FakeUserConnection(cursor)
            with patch("main.get_connection", return_value=connection):
                with self.assertRaises(HTTPException) as error:
                    create_company_user(
                        self.company_user_payload(), 1, {"role_name": "SUPER_ADMIN"}
                    )
            self.assertEqual(error.exception.status_code, 409)
            self.assertIn(expected, error.exception.detail)
            self.assertTrue(connection.rolled_back)
            self.assertFalse(connection.committed)

    def test_unknown_inactive_company_and_missing_role_are_rejected(self):
        for cursor, expected_status in (
            (FakeUserCursor(company_status=None), 404),
            (FakeUserCursor(company_status="INACTIVE"), 409),
            (FakeUserCursor(role_id=None), 500),
        ):
            connection = FakeUserConnection(cursor)
            with patch("main.get_connection", return_value=connection):
                with self.assertRaises(HTTPException) as error:
                    create_company_user(
                        self.company_user_payload(), 1, {"role_name": "SUPER_ADMIN"}
                    )
            self.assertEqual(error.exception.status_code, expected_status)
            self.assertTrue(connection.rolled_back)
            self.assertFalse(connection.committed)

    def test_insert_trigger_or_database_failure_is_safe_and_rolled_back(self):
        cursor = FakeUserCursor(
            insert_error=main.pyodbc.DatabaseError("SQL Server trigger failure 51001")
        )
        connection = FakeUserConnection(cursor)
        with patch("main.get_connection", return_value=connection):
            with self.assertRaises(HTTPException) as error:
                create_company_user(
                    self.company_user_payload(), 1, {"role_name": "SUPER_ADMIN"}
                )
        self.assertEqual(error.exception.status_code, 500)
        self.assertNotIn("51001", error.exception.detail)
        self.assertTrue(connection.rolled_back)
        self.assertFalse(connection.committed)

    def test_only_super_admin_can_provision_company_users(self):
        with self.assertRaises(HTTPException) as error:
            require_super_admin({"role_name": "COMPANY_ADMIN"})
        self.assertEqual(error.exception.status_code, 403)

    def test_product_schema_rejects_negative_threshold_and_client_tenant(self):
        valid = {
            "sku": "fabric-001",
            "product_name": "Cotton fabric",
            "product_type": "RAW_MATERIAL",
            "unit_id": 1,
        }
        with self.assertRaises(ValidationError):
            ProductCreate(**{**valid, "reorder_level": -1})
        with self.assertRaises(ValidationError):
            ProductCreate(**{**valid, "company_id": 99})
        product = ProductCreate(**valid)
        self.assertEqual(product.sku, "FABRIC-001")
        self.assertEqual(product.reorder_level, 0)


if __name__ == "__main__":
    unittest.main()
