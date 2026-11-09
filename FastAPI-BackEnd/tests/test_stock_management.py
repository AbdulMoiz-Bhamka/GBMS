import unittest
from contextlib import nullcontext
from decimal import Decimal
from uuid import uuid4
from unittest.mock import patch

from fastapi import HTTPException
from app.main import app
from app.core.permissions import COMPANY_ADMIN_PERMISSIONS
from app.dependencies.permissions import require_company_permission
from app.modules.inventory import repository, service
from app.modules.inventory.schemas import ProductUpdate, StockReceiptCreate

class Connection:
    def __init__(self): self.committed = False
    def commit(self): self.committed = True

class Cursor:
    rowcount = 1

class StockManagementTests(unittest.TestCase):
    def test_stock_routes_and_admin_permissions_are_registered(self):
        paths = app.openapi()['paths']
        for path in (
            '/api/v1/inventory/products/{product_id}/stock/receipts',
            '/api/v1/inventory/products/{product_id}/stock/transactions',
            '/api/v1/inventory/low-stock/count',
        ):
            self.assertIn(path, paths)
        self.assertTrue({'inventory.stock.receive','inventory.stock.issue','inventory.stock.adjust'} <= COMPANY_ADMIN_PERMISSIONS)

    def test_product_update_cannot_change_quantity_directly(self):
        with self.assertRaises(Exception):
            ProductUpdate(quantity_on_hand=500)

    def test_receipt_permission_rejects_users_without_the_grant(self):
        dependency = require_company_permission('inventory.stock.receive')
        with self.assertRaises(HTTPException) as error:
            dependency(user={'company_id': 8, 'permissions': ['inventory.view']})
        self.assertEqual(error.exception.status_code, 403)

    def test_receipt_schema_requires_positive_quantity_and_idempotency_key(self):
        with self.assertRaises(Exception):
            StockReceiptCreate(received_quantity=0)
        with self.assertRaises(Exception):
            StockReceiptCreate(received_quantity=1)

    def test_receipt_updates_company_product_and_writes_ledger_atomically(self):
        connection, cursor, key = Connection(), Cursor(), uuid4()
        product = (17, 'RAW_MATERIAL', 1, Decimal('4.000'), Decimal('2.000'), True)
        ledger = (91, 8, 17, 'STOCK_RECEIPT', Decimal('3.000'), Decimal('4.000'), Decimal('7.000'), None, None, 'INV-1', 51, None, 'receipt')
        with patch.object(service, 'database_connection', return_value=nullcontext(connection)), \
             patch.object(service, 'database_cursor', return_value=nullcontext(cursor)), \
             patch.object(repository, 'get_idempotent_transaction', return_value=None) as idem, \
             patch.object(repository, 'get_product_stock_for_update', return_value=product) as locked, \
             patch.object(repository, 'update_stock_balance', return_value=cursor) as update, \
             patch.object(repository, 'insert_inventory_transaction', return_value=ledger) as insert:
            result = service.record_stock_transaction(8, 17, 51, transaction_type='STOCK_RECEIPT', quantity_changed=Decimal('3'), idempotency_key=key, reference_number='INV-1', notes='receipt')
        self.assertEqual(result['new_balance'], Decimal('7.000'))
        self.assertTrue(connection.committed)
        idem.assert_called_once_with(cursor, 8, key)
        locked.assert_called_once_with(cursor, 8, 17)
        update.assert_called_once_with(cursor, 8, 17, Decimal('4.000'), Decimal('7.000'))
        insert.assert_called_once()

    def test_negative_stock_is_rejected_without_commit(self):
        connection, cursor = Connection(), Cursor()
        with patch.object(service, 'database_connection', return_value=nullcontext(connection)), \
             patch.object(service, 'database_cursor', return_value=nullcontext(cursor)), \
             patch.object(repository, 'get_idempotent_transaction', return_value=None), \
             patch.object(repository, 'get_product_stock_for_update', return_value=(17,'RAW_MATERIAL',1,Decimal('2'),Decimal('1'),True)):
            with self.assertRaises(HTTPException) as error:
                service.record_stock_transaction(8,17,51,transaction_type='STOCK_ISSUE',quantity_changed=Decimal('-3'),idempotency_key=uuid4())
        self.assertEqual(error.exception.status_code, 422)
        self.assertFalse(connection.committed)

    def test_replayed_request_key_returns_existing_entry_without_counting_twice(self):
        connection, cursor, key = Connection(), Cursor(), uuid4()
        existing = (90, 8, 17, 'STOCK_RECEIPT', Decimal('3'), Decimal('4'), Decimal('7'), None, None, 'INV-1', 51, None, 'receipt')
        with patch.object(service, 'database_connection', return_value=nullcontext(connection)), \
             patch.object(service, 'database_cursor', return_value=nullcontext(cursor)), \
             patch.object(repository, 'get_idempotent_transaction', return_value=existing), \
             patch.object(repository, 'get_product_stock_for_update') as lock, \
             patch.object(repository, 'update_stock_balance') as update:
            result = service.record_stock_transaction(8, 17, 51, transaction_type='STOCK_RECEIPT', quantity_changed=Decimal('3'), idempotency_key=key, reference_number='INV-1', notes='receipt')
        self.assertTrue(result['already_processed'])
        lock.assert_not_called()
        update.assert_not_called()
        self.assertFalse(connection.committed)

    def test_inventory_queries_are_company_scoped_for_low_stock_and_history(self):
        class QueryCursor:
            def __init__(self): self.calls=[]
            def execute(self, sql, *params): self.calls.append((sql,params)); return self
            def fetchone(self): return (0,)
            def fetchall(self): return []
        cursor=QueryCursor()
        repository.count_low_stock(cursor, 8)
        repository.list_stock_transactions(cursor,8,17,None,None,None,50,0)
        for sql, params in cursor.calls:
            self.assertIn('CompanyID = ?', sql)
            self.assertEqual(params[0],8)

if __name__ == '__main__': unittest.main()
