import unittest
from datetime import date
from decimal import Decimal

from fastapi import HTTPException
from pydantic import ValidationError

from app.core.permissions import COMPANY_ADMIN_PERMISSIONS, PERMISSION_LABELS
from app.main import app
from app.modules.purchasing import repository, service
from app.modules.purchasing.schemas import PurchaseOrderDraft


class Cursor:
    def __init__(self, one=None, rows=None):
        self.one = one
        self.rows = rows or []
        self.calls = []

    def execute(self, sql, *params):
        self.calls.append((sql, params))
        return self

    def fetchone(self):
        return self.one

    def fetchall(self):
        return self.rows


class PurchaseOrderTests(unittest.TestCase):
    def test_purchase_order_routes_are_registered(self):
        paths = app.openapi()["paths"]
        self.assertTrue({
            "/api/v1/purchase-orders", "/api/v1/purchase-orders/form-options",
            "/api/v1/purchase-orders/{purchase_order_id}",
            "/api/v1/purchase-orders/{purchase_order_id}/submit",
            "/api/v1/purchase-orders/{purchase_order_id}/cancel",
            "/api/v1/purchase-orders/{purchase_order_id}/print",
        }.issubset(paths))

    def test_draft_schema_rejects_invalid_prices_quantities_and_dates(self):
        valid = {
            "supplier_id": 2, "order_date": "2026-10-20",
            "items": [{"product_id": 5, "quantity": "2.5", "unit_cost": "150.25"}],
        }
        self.assertEqual(PurchaseOrderDraft(**valid).items[0].quantity, Decimal("2.5"))
        with self.assertRaises(ValidationError):
            PurchaseOrderDraft(**{**valid, "items": [{"product_id": 5, "quantity": 0, "unit_cost": 1}]})
        with self.assertRaises(ValidationError):
            PurchaseOrderDraft(**{**valid, "items": [{"product_id": 5, "quantity": 1, "unit_cost": -1}]})
        with self.assertRaises(ValidationError):
            PurchaseOrderDraft(**{**valid, "expected_delivery_date": "2026-10-19"})

    def test_total_is_derived_from_selected_company_products(self):
        cursor = Cursor(one=("FAB-01", "Cotton", 7, "KG", True, 9, None, None, None))
        payload = PurchaseOrderDraft(supplier_id=3, items=[
            {"product_id": 4, "quantity": "2.500", "unit_cost": "10.10"},
            {"product_id": 4, "quantity": "1", "unit_cost": "4.25"},
        ])
        prepared, subtotal = service._prepare_items(cursor, 9, payload.items)
        self.assertEqual(subtotal, Decimal("29.50"))
        self.assertEqual(prepared[0]["line_total"], Decimal("25.25"))
        self.assertEqual(cursor.calls[0][1], (9, 4))

    def test_product_validation_rejects_other_company_or_inactive_items(self):
        payload = PurchaseOrderDraft(supplier_id=3, items=[
            {"product_id": 4, "quantity": "1", "unit_cost": "1"},
        ])
        for row in (
            None,
            ("FAB", "Cotton", 7, "KG", False, 8, None, None, None),
            ("FAB", "Cotton", 7, "KG", True, 9, None, None, None),
        ):
            with self.subTest(row=row):
                with self.assertRaises(HTTPException) as error:
                    service._prepare_items(Cursor(one=row), 8, payload.items)
                self.assertEqual(error.exception.status_code, 422)

    def test_order_list_is_company_scoped_and_parameterized(self):
        cursor = Cursor(one=(0,), rows=[])
        repository.list_company_orders(
            cursor, 15, "PO-2026", 4, "DRAFT", date(2026, 1, 1),
            date(2026, 12, 31), 20, 40,
        )
        self.assertEqual(len(cursor.calls), 2)
        sql, params = cursor.calls[1]
        self.assertIn("po.CompanyID = ?", sql)
        self.assertIn("po.SupplierID = ?", sql)
        self.assertEqual(params, (15, "%PO-2026%", 4, "DRAFT", date(2026, 1, 1), date(2026, 12, 31), 40, 20))

    def test_purchase_order_numbers_use_a_database_sequence(self):
        cursor = Cursor(one=(102,))
        self.assertEqual(repository.next_order_number_value(cursor), 102)
        self.assertIn("NEXT VALUE FOR dbo.PurchaseOrderNumberSequence", cursor.calls[0][0])

    def test_company_admin_and_permission_catalog_include_purchasing_actions(self):
        required = {"purchasing.view", "purchasing.create", "purchasing.update",
                    "purchasing.submit", "purchasing.cancel"}
        self.assertTrue(required.issubset(COMPANY_ADMIN_PERMISSIONS))
        self.assertTrue(required.issubset(PERMISSION_LABELS))

    def test_purchase_order_line_writes_never_update_inventory(self):
        cursor = Cursor()
        repository.insert_order_item(
            cursor, company_id=2, purchase_order_id=10, product_id=9,
            sku="FAB-01", product_name="Cotton", unit_code="M", quantity=Decimal("2"),
            unit_cost=Decimal("4"), line_total=Decimal("8"),
        )
        sql = cursor.calls[0][0].upper()
        self.assertIn("INSERT INTO DBO.PURCHASEORDERITEMS", sql)
        self.assertNotIn("UPDATE DBO.PRODUCTS", sql)
        self.assertNotIn("QUANTITYONHAND", sql)

