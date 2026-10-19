"""Database-free validation and tenant-scope checks for supplier management."""

import unittest
from contextlib import nullcontext
from unittest.mock import patch

import pyodbc
from fastapi import HTTPException
from pydantic import ValidationError

from app.core.permissions import COMPANY_ADMIN_PERMISSIONS, effective_permissions
from app.main import app
from app.modules.suppliers import repository, service
from app.modules.suppliers.schemas import SupplierCreate, SupplierStatusUpdate, SupplierUpdate


class RecordingCursor:
    def __init__(self, *, supplier=None, error=None):
        self.supplier = supplier
        self.error = error
        self.calls = []
        self.rowcount = 1

    def execute(self, sql, *params):
        self.calls.append((sql, params))
        if self.error:
            raise self.error
        return self

    def fetchone(self):
        return self.supplier

    def fetchall(self):
        return []


class QueueCursor(RecordingCursor):
    def __init__(self, one_rows=(), many_rows=()):
        super().__init__()
        self.one_rows = list(one_rows)
        self.many_rows = list(many_rows)

    def fetchone(self):
        return self.one_rows.pop(0)

    def fetchall(self):
        return self.many_rows.pop(0)


class RecordingConnection:
    def __init__(self):
        self.committed = False
        self.rolled_back = False

    def commit(self):
        self.committed = True

    def rollback(self):
        self.rolled_back = True

    def close(self):
        pass


class SupplierManagementTests(unittest.TestCase):
    def test_supplier_routes_are_registered(self):
        paths = app.openapi()["paths"]
        self.assertTrue(
            {
                "/api/v1/suppliers",
                "/api/v1/suppliers/{supplier_id}",
                "/api/v1/suppliers/{supplier_id}/status",
            }.issubset(paths)
        )
        self.assertEqual(
            {"get", "post"},
            {method for method in paths["/api/v1/suppliers"]},
        )

    def test_supplier_create_normalizes_code_and_optional_fields(self):
        supplier = SupplierCreate(
            supplier_code=" fabric-01 ",
            supplier_name="  Lahore Fabrics  ",
            email=" sales@example.com ",
            phone="   ",
        )
        self.assertEqual(supplier.supplier_code, "FABRIC-01")
        self.assertEqual(supplier.supplier_name, "Lahore Fabrics")
        self.assertEqual(supplier.email, "sales@example.com")
        self.assertIsNone(supplier.phone)

    def test_supplier_rejects_invalid_email_and_client_company_id(self):
        with self.assertRaises(ValidationError):
            SupplierCreate(supplier_code="FAB-01", supplier_name="Fabric", email="bad-email")
        with self.assertRaises(ValidationError):
            SupplierCreate(
                supplier_code="FAB-01", supplier_name="Fabric", company_id=999
            )

    def test_status_is_restricted_to_active_or_inactive(self):
        self.assertEqual(SupplierStatusUpdate(supplier_status="ACTIVE").supplier_status, "ACTIVE")
        with self.assertRaises(ValidationError):
            SupplierStatusUpdate(supplier_status="DELETED")

    def test_company_admin_default_access_includes_supplier_management(self):
        permissions = effective_permissions("COMPANY_ADMIN", False)
        self.assertTrue(
            {"suppliers.view", "suppliers.create", "suppliers.update", "suppliers.deactivate"}
            .issubset(set(permissions))
        )
        self.assertTrue({"suppliers.view", "suppliers.create"}.issubset(COMPANY_ADMIN_PERMISSIONS))

    def test_supplier_list_query_is_company_scoped_and_parameterized(self):
        cursor = RecordingCursor(supplier=(3,))
        repository.list_suppliers(cursor, 12, "cloth", "ACTIVE", 20, 40)
        self.assertEqual(len(cursor.calls), 2)
        sql, params = cursor.calls[0]
        self.assertIn("CompanyID = ?", sql)
        self.assertIn("SupplierStatus = ?", sql)
        self.assertEqual(params[0], 12)
        self.assertEqual(params[-1], "ACTIVE")
        self.assertIn("SupplierCode LIKE ?", cursor.calls[0][0])
        self.assertEqual(cursor.calls[1][1][-2:], (40, 20))

    def test_detail_query_cannot_cross_company(self):
        cursor = RecordingCursor()
        repository.get_supplier(cursor, 12, 77)
        sql, params = cursor.calls[0]
        self.assertIn("WHERE CompanyID = ? AND SupplierID = ?", sql)
        self.assertEqual(params, (12, 77))

    def test_duplicate_code_is_reported_as_conflict(self):
        cursor = RecordingCursor(error=pyodbc.IntegrityError("2627 duplicate key"))
        connection = RecordingConnection()
        payload = SupplierCreate(supplier_code="FAB-01", supplier_name="Fabric")
        with patch.object(service, "database_connection", return_value=nullcontext(connection)):
            with patch.object(service, "database_cursor", return_value=nullcontext(cursor)):
                with self.assertRaises(HTTPException) as raised:
                    service.create_supplier(12, payload)
        self.assertEqual(raised.exception.status_code, 409)
        self.assertFalse(connection.committed)

    def test_missing_supplier_in_company_scope_is_not_found(self):
        cursor = RecordingCursor(supplier=None)
        connection = RecordingConnection()
        with patch.object(service, "database_connection", return_value=nullcontext(connection)):
            with patch.object(service, "database_cursor", return_value=nullcontext(cursor)):
                with self.assertRaises(HTTPException) as raised:
                    service.get_supplier(12, 77)
        self.assertEqual(raised.exception.status_code, 404)
        self.assertEqual(cursor.calls[0][1], (12, 77))

    def test_company_scoped_create_returns_saved_supplier_and_commits(self):
        row = (77, "FAB-01", "Lahore Fabrics", None, None, None, None, None, None, None, None, None, None, "ACTIVE", None, None)
        cursor = QueueCursor(one_rows=[(77,), row])
        connection = RecordingConnection()
        payload = SupplierCreate(supplier_code="fab-01", supplier_name="Lahore Fabrics")
        with patch.object(service, "database_connection", return_value=nullcontext(connection)):
            with patch.object(service, "database_cursor", return_value=nullcontext(cursor)):
                created = service.create_supplier(12, payload)
        self.assertEqual(created["supplier_id"], 77)
        self.assertEqual(cursor.calls[0][1][0], 12)
        self.assertTrue(connection.committed)

    def test_list_service_returns_company_filtered_pagination(self):
        row = (77, "FAB-01", "Lahore Fabrics", None, None, None, None, None, None, None, None, None, None, "ACTIVE", None, None)
        cursor = QueueCursor(one_rows=[(1,)], many_rows=[[row]])
        connection = RecordingConnection()
        with patch.object(service, "database_connection", return_value=nullcontext(connection)):
            with patch.object(service, "database_cursor", return_value=nullcontext(cursor)):
                result = service.list_suppliers(12, "", "ACTIVE", 20, 0)
        self.assertEqual(result["total"], 1)
        self.assertEqual(result["items"][0]["supplier_code"], "FAB-01")
        self.assertEqual(cursor.calls[0][1], (12, "ACTIVE"))

    def test_update_and_status_changes_commit_with_company_scope(self):
        row = (77, "FAB-01", "Lahore Fabrics", None, None, None, None, None, None, None, None, None, None, "ACTIVE", None, None)
        update_cursor = QueueCursor(one_rows=[row, row])
        update_connection = RecordingConnection()
        payload = SupplierUpdate(supplier_name="New Fabric Name")
        with patch.object(service, "database_connection", return_value=nullcontext(update_connection)):
            with patch.object(service, "database_cursor", return_value=nullcontext(update_cursor)):
                service.update_supplier(12, 77, payload)
        self.assertEqual(update_cursor.calls[1][1][-2:], (12, 77))
        self.assertTrue(update_connection.committed)

        status_cursor = QueueCursor(one_rows=[row])
        status_connection = RecordingConnection()
        with patch.object(service, "database_connection", return_value=nullcontext(status_connection)):
            with patch.object(service, "database_cursor", return_value=nullcontext(status_cursor)):
                result = service.set_supplier_status(12, 77, "INACTIVE")
        self.assertEqual(result["supplier_id"], 77)
        self.assertEqual(status_cursor.calls[0][1], ("INACTIVE", 12, 77))
        self.assertTrue(status_connection.committed)

    def test_update_rejects_empty_patch(self):
        payload = SupplierUpdate()
        with self.assertRaises(HTTPException) as raised:
            service.update_supplier(12, 77, payload)
        self.assertEqual(raised.exception.status_code, 400)


if __name__ == "__main__":
    unittest.main()
