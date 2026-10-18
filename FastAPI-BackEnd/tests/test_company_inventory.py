# test_company_inventory.py
"""Focused, database-free checks for tenant authorization and request schemas."""

import unittest
from unittest.mock import patch

from fastapi import HTTPException
from pydantic import ValidationError

import pyodbc
from app.core.config import ALLOWED_ORIGINS
from app.dependencies.permissions import require_company_user, require_super_admin
from app.dependencies.permissions import has_permission
from app.core.permissions import effective_permissions
from app.modules.companies.schemas import CompanyCreate
from app.modules.inventory.repository import category_available
from app.modules.inventory.service import _ensure_category
from app.modules.inventory.schemas import ProductCreate
from app.modules.users.schemas import CompanyUserCreate, CompanyUserUpdate
from app.modules.users.service import (
    _company_for_actor,
    _require,
    create_company_user,
    validate_role_company,
)
from app.main import app


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
        self.permission_rows = []
        self.insert_sql = None
        self.insert_params = None

    def execute(self, sql, *params):
        normalized = " ".join(sql.split()).upper()
        if "SELECT COMPANYSTATUS FROM DBO.COMPANIES" in normalized:
            self.result = (self.company_status,) if self.company_status else None
        elif "SELECT ROLEID FROM DBO.ROLES" in normalized:
            self.result = (self.role_id,) if self.role_id else None
        elif "INSERT INTO DBO.USERS" in normalized:
            self.insert_sql = normalized
            self.insert_params = params
            if self.insert_error:
                raise self.insert_error
            if "SCOPE_IDENTITY()" not in normalized:
                raise AssertionError("SCOPE_IDENTITY must run in the INSERT batch.")
            self.result = (77,)
        elif "FROM DBO.USERS AS U JOIN DBO.ROLES AS R" in normalized and "WHERE U.COMPANYID = ? AND U.USERID = ?" in normalized:
            self.result = (77, "aman365", "Aman", "aman@example.com", "INVENTORY_USER", "ACTIVE", 1, "2026-10-13", 1)
        elif "FROM DBO.USERPERMISSIONS" in normalized:
            self.rows = list(self.permission_rows)
            self.result = None
        elif "DELETE FROM DBO.USERPERMISSIONS" in normalized:
            self.result = None
        elif "INSERT INTO DBO.USERPERMISSIONS" in normalized:
            self.permission_rows.append((params[1],))
            self.result = None
        else:
            raise AssertionError(f"Unexpected SQL in fake cursor: {normalized}")
        return self

    def fetchone(self):
        return self.result

    def fetchall(self):
        return getattr(self, "rows", [])

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
    def test_modular_app_registers_existing_api_paths(self):
        paths = set(app.openapi()["paths"])
        self.assertTrue(
            {
                "/health",
                "/api/v1/auth/login",
                "/api/v1/auth/me",
                "/api/v1/dashboard",
                "/api/v1/companies",
                "/api/v1/companies/{company_id}/users",
                "/api/v1/companies/{company_id}/users/{user_id}",
                "/api/v1/companies/{company_id}/users/{user_id}/status",
                "/api/v1/users/assignable-options",
                "/api/v1/inventory/categories",
                "/api/v1/inventory/products",
            }.issubset(paths)
        )

    def test_local_frontend_origins_are_always_allowed(self):
        self.assertIn("http://localhost:5173", ALLOWED_ORIGINS)
        self.assertIn("http://127.0.0.1:5173", ALLOWED_ORIGINS)

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

    def test_user_permissions_are_individual_and_role_scoped(self):
        selected = effective_permissions("INVENTORY_USER", True, ["inventory.view"])
        self.assertIn("dashboard.view", selected)
        self.assertIn("inventory.view", selected)
        self.assertNotIn("inventory.update", selected)
        self.assertTrue(has_permission({"role_name": "INVENTORY_USER", "permissions": selected}, "inventory.view"))
        self.assertFalse(has_permission({"role_name": "INVENTORY_USER", "permissions": selected}, "users.create"))
        self.assertTrue(has_permission({"role_name": "COMPANY_ADMIN", "permissions": []}, "users.create"))
        self.assertEqual(effective_permissions("UNLISTED_ROLE", False), ["dashboard.view"])

    def test_company_user_operations_reject_a_different_tenant(self):
        actor = {"user_id": 20, "role_name": "COMPANY_ADMIN", "company_id": 8}
        with self.assertRaises(HTTPException) as error:
            _company_for_actor(actor, 9)
        self.assertEqual(error.exception.status_code, 404)

    def test_company_admin_cannot_create_another_company_admin(self):
        actor = {
            "user_id": 20,
            "role_name": "COMPANY_ADMIN",
            "company_id": 8,
            "permissions": effective_permissions("COMPANY_ADMIN", True),
        }
        payload = CompanyUserCreate(
            username="another_admin",
            full_name="Another Admin",
            email="another@example.com",
            password="a-secure-test-password",
            role_name="COMPANY_ADMIN",
        )
        with self.assertRaises(HTTPException) as error:
            create_company_user(actor, 8, payload)
        self.assertEqual(error.exception.status_code, 403)

    def test_user_cannot_grant_permissions_they_do_not_have(self):
        actor = {
            "user_id": 20,
            "role_name": "SUB_ADMIN",
            "company_id": 8,
            "permissions": ["dashboard.view", "users.create", "users.assign_role"],
        }
        payload = CompanyUserCreate(
            username="limited_user",
            full_name="Limited User",
            email="limited@example.com",
            password="a-secure-test-password",
            role_name="INVENTORY_USER",
            permission_codes=["inventory.update"],
        )
        with self.assertRaises(HTTPException) as error:
            create_company_user(actor, 8, payload)
        self.assertEqual(error.exception.status_code, 403)

    def test_permission_checks_reject_unassigned_actions(self):
        user = {"role_name": "INVENTORY_USER", "permissions": ["dashboard.view", "inventory.view"]}
        with self.assertRaises(HTTPException) as error:
            _require(user, "inventory.create")
        self.assertEqual(error.exception.status_code, 403)

    def test_inventory_access_is_not_granted_to_platform_or_unlisted_roles(self):
        with self.assertRaises(HTTPException) as platform_user:
            require_company_user({"role_name": "SUPER_ADMIN", "company_id": None})
        self.assertEqual(platform_user.exception.status_code, 403)
        with self.assertRaises(HTTPException) as unlisted_role:
            require_company_user({"role_name": "HR_USER", "company_id": 12})
        self.assertEqual(unlisted_role.exception.status_code, 403)

    def test_category_lookup_is_scoped_to_company(self):
        cursor = FakeCategoryCursor(found=True)
        category_available(cursor, 4, 12)
        self.assertIn("CategoryID = ? AND CompanyID = ?", cursor.sql)
        self.assertEqual(cursor.params, (4, 12))

    def test_missing_cross_company_category_is_rejected(self):
        with self.assertRaises(HTTPException) as error:
            _ensure_category(FakeCategoryCursor(found=False), 4, 12)
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
            CompanyUserUpdate(role_name="SUPER_ADMIN")
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
            role_name="INVENTORY_USER",
            permission_codes=["inventory.view", "inventory.create"],
        )

    def call_create_company_user(self, cursor, company_id=1):
        connection = FakeUserConnection(cursor)
        with patch("app.db.connection.get_connection", return_value=connection):
            response = create_company_user(
                {"user_id": 1, "role_name": "SUPER_ADMIN", "company_id": None},
                company_id,
                self.company_user_payload(),
            )
        return response, connection

    def test_company_user_creation_uses_trigger_compatible_insert_and_hashes_password(self):
        cursor = FakeUserCursor()
        response, connection = self.call_create_company_user(cursor)
        self.assertEqual(response["user_id"], 77)
        self.assertEqual(response["permission_codes"], ["dashboard.view", "inventory.create", "inventory.view"])
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
                insert_error=pyodbc.IntegrityError(
                    f"2627 duplicate key in {constraint}"
                )
            )
            connection = FakeUserConnection(cursor)
            with patch("app.db.connection.get_connection", return_value=connection):
                with self.assertRaises(HTTPException) as error:
                    create_company_user(
                        {"user_id": 1, "role_name": "SUPER_ADMIN", "company_id": None}, 1,
                        self.company_user_payload(),
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
            with patch("app.db.connection.get_connection", return_value=connection):
                with self.assertRaises(HTTPException) as error:
                    create_company_user(
                        {"user_id": 1, "role_name": "SUPER_ADMIN", "company_id": None}, 1,
                        self.company_user_payload(),
                    )
            self.assertEqual(error.exception.status_code, expected_status)
            self.assertTrue(connection.rolled_back)
            self.assertFalse(connection.committed)

    def test_insert_trigger_or_database_failure_is_safe_and_rolled_back(self):
        cursor = FakeUserCursor(
            insert_error=pyodbc.DatabaseError("SQL Server trigger failure 51001")
        )
        connection = FakeUserConnection(cursor)
        with patch("app.db.connection.get_connection", return_value=connection):
            with self.assertRaises(HTTPException) as error:
                create_company_user(
                    {"user_id": 1, "role_name": "SUPER_ADMIN", "company_id": None}, 1,
                    self.company_user_payload(),
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
