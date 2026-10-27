import base64
import unittest
from contextlib import nullcontext
from unittest.mock import patch

from fastapi import HTTPException

from app.main import app
from app.core.permissions import COMPANY_ADMIN_PERMISSIONS, PERMISSION_LABELS
from app.dependencies.permissions import require_company_permission
from app.modules.inventory import repository, service
from app.modules.inventory.schemas import ProductCreate, ProductUpdate


class Cursor:
    def __init__(self, row):
        self.row = row
        self.calls = []
        self.rowcount = 1

    def execute(self, sql, *params):
        self.calls.append((sql, params))
        if "SET BARCODEVALUE" in sql.upper():
            self.row = (*self.row[:8], params[0], *self.row[9:])
        return self

    def fetchone(self):
        return self.row

    def fetchall(self):
        return []


class Connection:
    def __init__(self):
        self.committed = False

    def commit(self):
        self.committed = True

    def rollback(self):
        pass

    def close(self):
        pass


class BarcodeTests(unittest.TestCase):
    def test_barcode_routes_are_registered(self):
        paths = app.openapi()["paths"]
        self.assertIn("/api/v1/inventory/products/{product_id}/barcode", paths)
        self.assertIn("get", paths["/api/v1/inventory/products/{product_id}/barcode"])
        self.assertIn("post", paths["/api/v1/inventory/products/{product_id}/barcode"])
        self.assertIn("/api/v1/inventory/barcodes/{barcode_value}", paths)

    def test_code128_svg_is_generated_by_real_barcode_library(self):
        encoded = service._barcode_svg("GBMS0000010123456789ABCDEF")
        svg = base64.b64decode(encoded).decode("utf-8")
        self.assertIn("<svg", svg)
        self.assertIn("GBMS0000010123456789ABCDEF", svg)
        self.assertIn("<rect", svg)

    def test_finished_good_gets_unique_stable_barcode_and_label(self):
        row = (42, "TSH-001-M", "Cotton T-shirt", "FINISHED_GOOD", "Classic", "M", "Navy", 1200.00, None, True)
        cursor = Cursor(row)
        connection = Connection()
        with patch.object(service, "database_connection", return_value=nullcontext(connection)), \
             patch.object(service, "database_cursor", return_value=nullcontext(cursor)), \
             patch.object(service.secrets, "token_hex", return_value="ABCDEF0123456789ABCD"):
            result = service.generate_product_barcode(1, 42)
        self.assertEqual(result["barcode_value"], "GBMS000001ABCDEF0123456789ABCD")
        self.assertEqual(result["product_id"], 42)
        self.assertTrue(result["barcode_svg_base64"])
        self.assertNotIn("1200", base64.b64decode(result["barcode_svg_base64"]).decode("utf-8"))
        self.assertTrue(connection.committed)
        update_sql = next(sql for sql, _ in cursor.calls if "SET BarcodeValue" in sql)
        self.assertIn("CompanyID = ?", update_sql)
        self.assertNotIn("QuantityOnHand", update_sql)

    def test_existing_barcode_is_reused_for_printing_without_a_write(self):
        barcode_value = "GBMS0000010123456789ABCDEF"
        row = (42, "TSH-001-M", "Cotton T-shirt", "FINISHED_GOOD", "Classic", "M", "Navy", 1200.00, barcode_value, False)
        cursor = Cursor(row)
        connection = Connection()
        with patch.object(service, "database_connection", return_value=nullcontext(connection)), \
             patch.object(service, "database_cursor", return_value=nullcontext(cursor)):
            result = service.generate_product_barcode(1, 42)
        self.assertEqual(result["barcode_value"], barcode_value)
        self.assertEqual(result["selling_price"], 1200.00)
        self.assertTrue(result["barcode_svg_base64"])
        self.assertFalse(any("SET BarcodeValue" in sql for sql, _ in cursor.calls))
        self.assertFalse(connection.committed)

    def test_print_label_reads_existing_company_product_without_generating(self):
        barcode_value = "GBMS0000010123456789ABCDEF"
        row = (42, "TSH-001-M", "Cotton T-shirt", "FINISHED_GOOD", "Classic", "M", "Navy", 1200.00, barcode_value, False)
        cursor = Cursor(row)
        with patch.object(service, "database_connection", return_value=nullcontext(Connection())), \
             patch.object(service, "database_cursor", return_value=nullcontext(cursor)), \
             patch.object(repository, "get_barcode_product", return_value=row) as get_product:
            result = service.get_product_barcode_label(7, 42)
        get_product.assert_called_once_with(cursor, 7, 42)
        self.assertEqual(result["barcode_value"], barcode_value)
        self.assertEqual(result["variant_color"], "Navy")
        self.assertTrue(result["barcode_svg_base64"])

    def test_print_label_requires_a_preexisting_barcode(self):
        row = (42, "TSH-001-M", "Cotton T-shirt", "FINISHED_GOOD", "Classic", "M", "Navy", 1200.00, None, True)
        with patch.object(service, "database_connection", return_value=nullcontext(Connection())), \
             patch.object(service, "database_cursor", return_value=nullcontext(Cursor(row))), \
             patch.object(repository, "get_barcode_product", return_value=row):
            with self.assertRaises(HTTPException) as error:
                service.get_product_barcode_label(7, 42)
        self.assertEqual(error.exception.status_code, 409)

    def test_barcoded_product_cannot_clear_its_printed_selling_price(self):
        row = (42, "TSH-001-M", "Cotton T-shirt", "FINISHED_GOOD", 3, "Tops", 1,
               "PC", "Piece", None, 0, True, None, None, 0, "Classic", "M",
               "Navy", 1200.00, "GBMS0000010123456789ABCDEF")
        with patch.object(service, "database_connection", return_value=nullcontext(Connection())), \
             patch.object(service, "database_cursor", return_value=nullcontext(Cursor(row))), \
             patch.object(repository, "get_company_product", return_value=row), \
             patch.object(repository, "update_product") as update_product:
            with self.assertRaises(HTTPException) as error:
                service.update_product(7, 42, ProductUpdate(selling_price=None))
        self.assertEqual(error.exception.status_code, 409)
        update_product.assert_not_called()

    def test_barcode_generation_rejects_raw_materials_without_writing(self):
        row = (42, "FAB-01", "Cotton fabric", "RAW_MATERIAL", None, None, None, None, None, True)
        cursor = Cursor(row)
        connection = Connection()
        with patch.object(service, "database_connection", return_value=nullcontext(connection)), \
             patch.object(service, "database_cursor", return_value=nullcontext(cursor)):
            with self.assertRaises(HTTPException) as error:
                service.generate_product_barcode(1, 42)
        self.assertEqual(error.exception.status_code, 422)
        self.assertEqual(len(cursor.calls), 1)
        self.assertFalse(connection.committed)

    def test_barcode_generation_requires_configured_selling_price(self):
        row = (42, "TSH-001-M", "Cotton T-shirt", "FINISHED_GOOD", None, "M", None, None, None, True)
        cursor = Cursor(row)
        connection = Connection()
        with patch.object(service, "database_connection", return_value=nullcontext(connection)), \
             patch.object(service, "database_cursor", return_value=nullcontext(cursor)):
            with self.assertRaises(HTTPException) as error:
                service.generate_product_barcode(1, 42)
        self.assertEqual(error.exception.status_code, 422)
        self.assertEqual(len(cursor.calls), 1)

    def test_barcode_lookup_is_company_scoped(self):
        cursor = Cursor(None)
        repository.find_product_by_barcode(cursor, 8, "GBMS0000080123456789ABCDEF")
        self.assertIn("p.CompanyID = ? AND p.BarcodeValue = ?", cursor.calls[0][0])
        self.assertEqual(cursor.calls[0][1], (8, "GBMS0000080123456789ABCDEF"))

    def test_product_lookup_by_barcode_returns_company_product(self):
        row = (42, "TSH-001-M", "Cotton T-shirt", "FINISHED_GOOD", 3, "Tops", 1,
               "PC", "Piece", None, 0, True, None, None, 0, "Classic", "M",
               "Navy", 1200.00, "GBMS0000010123456789ABCDEF")
        cursor = Cursor(row)
        with patch.object(service, "database_connection", return_value=nullcontext(Connection())), \
             patch.object(service, "database_cursor", return_value=nullcontext(cursor)):
            product = service.lookup_product_barcode(1, row[19])
        self.assertEqual(product["product_id"], 42)
        self.assertEqual(product["selling_price"], 1200.00)
        self.assertEqual(cursor.calls[0][1], (1, row[19]))

    def test_catalogue_search_includes_barcode_and_company_scope(self):
        cursor = Cursor((0,))
        repository.list_products(cursor, 7, "GBMS000007", None, 25, 0)
        sql, params = cursor.calls[0]
        self.assertIn("p.BarcodeValue LIKE ?", sql)
        self.assertIn("p.CompanyID = ?", sql)
        self.assertEqual(params, (7, "%GBMS000007%", "%GBMS000007%", "%GBMS000007%"))

    def test_variant_and_selling_price_fields_are_supported(self):
        product = ProductCreate(
            sku="TSH-001-M", product_name="Cotton T-shirt", product_type="FINISHED_GOOD",
            unit_id=1, variant_design=" Classic ", variant_size=" M ",
            variant_color=" Navy ", selling_price="1200.00",
        )
        self.assertEqual(product.variant_design, "Classic")
        self.assertEqual(product.variant_size, "M")
        self.assertEqual(product.selling_price, 1200)

    def test_barcode_management_is_a_separate_company_permission(self):
        self.assertIn("inventory.barcode.manage", PERMISSION_LABELS)
        self.assertIn("inventory.barcode.manage", COMPANY_ADMIN_PERMISSIONS)
        dependency = require_company_permission("inventory.barcode.manage")
        permitted_user = {"company_id": 7, "permissions": ["inventory.barcode.manage"]}
        self.assertIs(dependency(user=permitted_user), permitted_user)
        with self.assertRaises(HTTPException) as error:
            dependency(user={"company_id": 7, "permissions": ["inventory.view"]})
        self.assertEqual(error.exception.status_code, 403)

    def test_barcode_generation_cannot_access_another_company_product(self):
        with patch.object(service, "database_connection", return_value=nullcontext(Connection())), \
             patch.object(service, "database_cursor", return_value=nullcontext(Cursor(None))), \
             patch.object(repository, "get_barcode_product", return_value=None) as get_product:
            with self.assertRaises(HTTPException) as error:
                service.generate_product_barcode(7, 42)
        get_product.assert_called_once()
        self.assertEqual(get_product.call_args.args[1:], (7, 42))
        self.assertEqual(error.exception.status_code, 404)

