import base64
import secrets
from decimal import Decimal
from uuid import uuid4

import barcode
import pyodbc
from barcode.writer import SVGWriter
from fastapi import HTTPException

from app.db.connection import database_connection, database_cursor
from app.modules.inventory import repository
from app.modules.inventory.schemas import (
    CompanyCategoryCreate,
    ProductCreate,
    ProductStatusUpdate,
    ProductUpdate,
)


def _integrity_error(exc, entity):
    if "2601" in str(exc) or "2627" in str(exc):
        raise HTTPException(
            status_code=409, detail=f"A {entity} with that name or code already exists."
        ) from exc
    raise HTTPException(
        status_code=500, detail=f"Could not save the {entity}. Please try again."
    ) from exc


def _ensure_category(cursor, category_id, company_id):
    if category_id is not None and not repository.category_available(cursor, category_id, company_id):
        raise HTTPException(
            status_code=422,
            detail="The selected category is not available to your company.",
        )


def _ensure_unit(cursor, unit_id):
    if not repository.active_unit_exists(cursor, unit_id):
        raise HTTPException(status_code=422, detail="Select a valid active unit of measure.")


def list_categories(company_id):
    with database_connection() as connection, database_cursor(connection) as cursor:
        rows = repository.list_categories(cursor, company_id)
    return [
        {"category_id": row[0], "category_name": row[1], "description": row[2]}
        for row in rows
    ]


def create_category(company_id, payload: CompanyCategoryCreate):
    with database_connection() as connection, database_cursor(connection) as cursor:
        try:
            row = repository.create_category(cursor, company_id, payload)
            connection.commit()
        except pyodbc.IntegrityError as exc:
            _integrity_error(exc, "category")
    return {"category_id": row[0], "category_name": row[1], "description": row[2]}


def list_units():
    with database_connection() as connection, database_cursor(connection) as cursor:
        rows = repository.list_units(cursor)
    return [
        {"unit_id": row[0], "unit_code": row[1], "unit_name": row[2], "symbol": row[3]}
        for row in rows
    ]


def list_products(company_id, search, category_id, limit, offset, low_stock_only=False, sort_by="name", product_type=None):
    with database_connection() as connection, database_cursor(connection) as cursor:
        rows, total = repository.list_products(
            cursor, company_id, search.strip(), category_id, limit, offset,
            low_stock_only, sort_by, product_type,
        )
    return {
        "items": [repository.serialize_product(row) for row in rows],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


def _get_company_product(cursor, company_id, product_id):
    row = repository.get_company_product(cursor, company_id, product_id)
    if not row:
        raise HTTPException(status_code=404, detail="Product not found.")
    return row


def _serialize_stock_transaction(row, already_processed=False):
    return {
        "transaction_id": row[0],
        "company_id": row[1],
        "product_id": row[2],
        "transaction_type": row[3],
        "quantity_changed": row[4],
        "previous_balance": row[5],
        "new_balance": row[6],
        "supplier_id": row[7],
        "purchase_order_id": row[8],
        "reference_number": row[9],
        "created_by_user_id": row[10],
        "transaction_at": row[11],
        "notes": row[12],
        "already_processed": already_processed,
    }


def record_stock_transaction(company_id, product_id, user_id, *, transaction_type,
                             quantity_changed, idempotency_key, supplier_id=None,
                             purchase_order_id=None, reference_number=None, notes=None):
    quantity_changed = Decimal(quantity_changed)
    if quantity_changed == 0:
        raise HTTPException(status_code=422, detail="Stock quantity must be greater than zero or less than zero for an adjustment.")
    with database_connection() as connection, database_cursor(connection) as cursor:
        existing_transaction = repository.get_idempotent_transaction(cursor, company_id, idempotency_key)
        if existing_transaction:
            same_request = (
                existing_transaction[2] == product_id
                and existing_transaction[3] == transaction_type
                and Decimal(existing_transaction[4]) == quantity_changed
                and existing_transaction[7] == supplier_id
                and existing_transaction[8] == purchase_order_id
                and existing_transaction[9] == reference_number
                and existing_transaction[12] == notes
            )
            if not same_request:
                raise HTTPException(status_code=409, detail="This stock request key was already used for a different request.")
            return _serialize_stock_transaction(existing_transaction, already_processed=True)

        product = repository.get_product_stock_for_update(cursor, company_id, product_id)
        if not product:
            raise HTTPException(status_code=404, detail="Product not found for this company.")
        if not bool(product[5]):
            raise HTTPException(status_code=409, detail="Activate the product before changing its stock.")
        previous_balance = Decimal(product[3])
        new_balance = previous_balance + quantity_changed
        if new_balance < 0:
            raise HTTPException(status_code=422, detail="The transaction would make stock negative.")

        if transaction_type == "STOCK_RECEIPT":
            if supplier_id is not None and not repository.supplier_is_active(cursor, company_id, supplier_id):
                raise HTTPException(status_code=422, detail="Select an active supplier from your company.")
            if purchase_order_id is not None:
                order = repository.get_receipt_purchase_order(cursor, company_id, purchase_order_id, product_id)
                if not order or order[1] not in {"SUBMITTED", "PARTIALLY_RECEIVED"}:
                    raise HTTPException(status_code=422, detail="Select an open purchase order from this company that contains this product.")
                if supplier_id is not None and order[0] != supplier_id:
                    raise HTTPException(status_code=422, detail="The selected supplier does not match the purchase order.")
                supplier_id = order[0]
                if not repository.supplier_belongs_to_company(cursor, company_id, supplier_id):
                    raise HTTPException(status_code=422, detail="The purchase order supplier is not available to this company.")
        elif supplier_id is not None or purchase_order_id is not None:
            raise HTTPException(status_code=422, detail="Supplier and purchase order references are only available for stock receipts.")

        updated = repository.update_stock_balance(
            cursor, company_id, product_id, previous_balance, new_balance
        )
        if updated.rowcount != 1:
            raise HTTPException(status_code=409, detail="Stock changed concurrently. Reload and submit again.")
        transaction = repository.insert_inventory_transaction(
            cursor, company_id=company_id, product_id=product_id,
            transaction_type=transaction_type, quantity_changed=quantity_changed,
            previous_balance=previous_balance, new_balance=new_balance,
            supplier_id=supplier_id, purchase_order_id=purchase_order_id,
            reference_number=reference_number, created_by_user_id=user_id,
            notes=notes, idempotency_key=idempotency_key,
        )
        connection.commit()
    return _serialize_stock_transaction(transaction)


def stock_transaction_history(company_id, product_id, transaction_type, date_from, date_to, limit, offset):
    with database_connection() as connection, database_cursor(connection) as cursor:
        _get_company_product(cursor, company_id, product_id)
        rows, total = repository.list_stock_transactions(
            cursor, company_id, product_id, transaction_type, date_from, date_to, limit, offset
        )
    return {
        "items": [{
            "transaction_id": r[0], "transaction_type": r[1], "quantity_changed": r[2],
            "previous_balance": r[3], "new_balance": r[4], "supplier_id": r[5],
            "supplier_name": r[6], "purchase_order_id": r[7], "purchase_order_number": r[8],
            "reference_number": r[9], "created_by_user_id": r[10], "created_by_name": r[11],
            "transaction_at": r[12], "notes": r[13],
        } for r in rows], "total": total, "limit": limit, "offset": offset,
    }


def low_stock_count(company_id):
    with database_connection() as connection, database_cursor(connection) as cursor:
        count = repository.count_low_stock(cursor, company_id)
    return {"count": int(count)}


def create_product(company_id, created_by_user_id, payload: ProductCreate):
    if payload.product_type == "RAW_MATERIAL" and payload.selling_price is not None:
        raise HTTPException(status_code=422, detail="Selling price is only available for finished goods.")
    with database_connection() as connection, database_cursor(connection) as cursor:
        _ensure_category(cursor, payload.category_id, company_id)
        _ensure_unit(cursor, payload.unit_id)
        try:
            product_id = repository.insert_product(cursor, company_id, payload)
            if payload.quantity_on_hand > 0:
                repository.insert_inventory_transaction(
                    cursor, company_id=company_id, product_id=product_id,
                    transaction_type="OPENING_STOCK", quantity_changed=payload.quantity_on_hand,
                    previous_balance=Decimal("0"), new_balance=payload.quantity_on_hand,
                    supplier_id=None, purchase_order_id=None, reference_number=None,
                    created_by_user_id=created_by_user_id, notes="Opening stock at product creation.",
                    idempotency_key=uuid4(),
                )
            row = _get_company_product(cursor, company_id, product_id)
            connection.commit()
        except pyodbc.IntegrityError as exc:
            _integrity_error(exc, "product SKU")
    return repository.serialize_product(row)


def get_product(company_id, product_id):
    with database_connection() as connection, database_cursor(connection) as cursor:
        row = _get_company_product(cursor, company_id, product_id)
    return repository.serialize_product(row)


def update_product(company_id, product_id, payload: ProductUpdate):
    values = payload.model_dump(exclude_unset=True)
    if not values:
        raise HTTPException(status_code=400, detail="Provide at least one product field to update.")
    non_nullable = {"sku", "product_name", "product_type", "unit_id", "reorder_level"}
    if any(values.get(key) is None for key in non_nullable if key in values):
        raise HTTPException(status_code=422, detail="Required product fields cannot be empty.")
    with database_connection() as connection, database_cursor(connection) as cursor:
        existing = _get_company_product(cursor, company_id, product_id)
        new_type = values.get("product_type", existing[3])
        new_price = values.get("selling_price", existing[18])
        if new_type == "RAW_MATERIAL" and new_price is not None:
            raise HTTPException(status_code=422, detail="Selling price is only available for finished goods.")
        if existing[19] and new_type != "FINISHED_GOOD":
            raise HTTPException(status_code=409, detail="A barcoded finished good cannot be changed to a raw material.")
        if existing[19] and "selling_price" in values and new_price is None:
            raise HTTPException(status_code=409, detail="A barcoded finished good must keep its selling price for label printing.")
        if "category_id" in values:
            _ensure_category(cursor, values["category_id"], company_id)
        if values.get("unit_id") is not None:
            _ensure_unit(cursor, values["unit_id"])
        try:
            repository.update_product(cursor, company_id, product_id, values)
            row = _get_company_product(cursor, company_id, product_id)
            connection.commit()
        except pyodbc.IntegrityError as exc:
            _integrity_error(exc, "product SKU")
    return repository.serialize_product(row)


def set_product_status(company_id, product_id, payload: ProductStatusUpdate):
    with database_connection() as connection, database_cursor(connection) as cursor:
        result = repository.update_product_status(
            cursor, company_id, product_id, payload.is_active
        )
        if result.rowcount == 0:
            raise HTTPException(status_code=404, detail="Product not found.")
        row = _get_company_product(cursor, company_id, product_id)
        connection.commit()
    return repository.serialize_product(row)


def _barcode_svg(value):
    rendered = barcode.get("code128", value, writer=SVGWriter()).render(
        writer_options={
            "module_width": 0.28,
            "module_height": 18,
            "quiet_zone": 4,
            "font_size": 10,
            "text_distance": 3,
            "background": "white",
            "foreground": "black",
        }
    )
    return base64.b64encode(rendered).decode("ascii")


def _serialize_barcode_product(row):
    return {
        "product_id": row[0], "sku": row[1], "product_name": row[2],
        "product_type": row[3], "variant_design": row[4],
        "variant_size": row[5], "variant_color": row[6],
        "selling_price": row[7], "barcode_value": row[8],
        "is_active": bool(row[9]),
    }


def _barcode_label(row):
    product = _serialize_barcode_product(row)
    product["barcode_svg_base64"] = _barcode_svg(product["barcode_value"])
    return product


def get_product_barcode_label(company_id, product_id):
    with database_connection() as connection, database_cursor(connection) as cursor:
        row = repository.get_barcode_product(cursor, company_id, product_id)
    if not row:
        raise HTTPException(status_code=404, detail="Product not found.")
    if row[3] != "FINISHED_GOOD":
        raise HTTPException(status_code=422, detail="Barcodes are only available for finished goods.")
    if row[8] is None:
        raise HTTPException(status_code=409, detail="Generate a barcode before printing its label.")
    return _barcode_label(row)


def generate_product_barcode(company_id, product_id, user_id=None):
    with database_connection() as connection, database_cursor(connection) as cursor:
        row = repository.get_barcode_product(cursor, company_id, product_id)
        if not row:
            raise HTTPException(status_code=404, detail="Product not found.")
        if row[3] != "FINISHED_GOOD":
            raise HTTPException(status_code=422, detail="Barcodes are only available for finished goods.")
        if row[8] is None:
            if not row[9]:
                raise HTTPException(status_code=409, detail="Activate this product before generating a barcode.")
            if row[7] is None:
                raise HTTPException(status_code=422, detail="Set a selling price before generating a barcode.")
            value = f"GBMS{company_id:06X}{secrets.token_hex(10).upper()}"
            try:
                result = repository.set_product_barcode(cursor, company_id, product_id, value, user_id)
            except pyodbc.IntegrityError as exc:
                raise HTTPException(status_code=409, detail="Barcode collision; retry generation.") from exc
            if result.rowcount != 1:
                row = repository.get_barcode_product(cursor, company_id, product_id)
                if not row or not row[8]:
                    raise HTTPException(status_code=409, detail="Could not assign the barcode; reload and try again.")
            else:
                row = repository.get_barcode_product(cursor, company_id, product_id)
            connection.commit()
    return _barcode_label(row)


def lookup_product_barcode(company_id, barcode_value):
    with database_connection() as connection, database_cursor(connection) as cursor:
        row = repository.find_product_by_barcode(cursor, company_id, barcode_value)
    if not row:
        raise HTTPException(status_code=404, detail="Barcode not found for this company.")
    return repository.serialize_product(row)
