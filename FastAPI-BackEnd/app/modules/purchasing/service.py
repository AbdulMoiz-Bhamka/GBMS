from decimal import Decimal, ROUND_HALF_UP

import pyodbc
from fastapi import HTTPException

from app.db.connection import database_connection, database_cursor
from app.modules.purchasing import repository
from app.modules.purchasing.schemas import PurchaseOrderDraft

CENT = Decimal("0.01")
MAX_MONEY = Decimal("99999999999999999.99")


def _money(value):
    result = value.quantize(CENT, rounding=ROUND_HALF_UP)
    if result > MAX_MONEY:
        raise HTTPException(status_code=422, detail="Purchase order amount exceeds the supported PKR limit.")
    return result


def _prepare_items(cursor, company_id, items):
    prepared = []
    subtotal = Decimal("0.00")
    for item in items:
        product = repository.get_order_product(cursor, company_id, item.product_id)
        if not product or not product[4] or product[5] != company_id:
            raise HTTPException(status_code=422, detail="A selected product is unavailable to your company.")
        line_total = _money(item.quantity * item.unit_cost)
        subtotal += line_total
        prepared.append({
            "product_id": item.product_id, "sku": product[0],
            "product_name": product[1], "unit_code": product[3],
            "variant_design": product[6], "variant_size": product[7],
            "variant_color": product[8],
            "quantity": item.quantity, "unit_cost": item.unit_cost,
            "line_total": line_total,
        })
    return prepared, _money(subtotal)


def _ensure_supplier(cursor, company_id, supplier_id):
    if not repository.supplier_is_active(cursor, company_id, supplier_id):
        raise HTTPException(status_code=422, detail="Select an active supplier belonging to your company.")


def _serialize_detail(cursor, company_id, order_row):
    order = repository.serialize_order(order_row)
    order["items"] = [
        {
            "purchase_order_item_id": row[0], "product_id": row[1],
            "sku": row[2], "product_name": row[3],
            "variant_design": row[4], "variant_size": row[5],
            "variant_color": row[6], "unit_code": row[7],
            "quantity": row[8], "unit_cost": row[9], "line_total": row[10],
        }
        for row in repository.list_order_items(cursor, company_id, order["purchase_order_id"])
    ]
    supplier = repository.supplier_details(cursor, company_id, order["supplier_id"])
    order["supplier_contact"] = {
        "name": supplier[0], "contact_person": supplier[1], "email": supplier[2],
        "phone": supplier[3], "address": supplier[4], "city": supplier[5],
        "country": supplier[6], "payment_terms": supplier[7],
    } if supplier else None
    order["status_history"] = [
        {"status": row[0], "changed_by_user_id": row[1], "changed_by_name": row[2],
         "note": row[3], "changed_at": row[4]}
        for row in repository.status_history(cursor, company_id, order["purchase_order_id"])
    ]
    order["item_count"] = len(order["items"])
    return order


def list_orders(company_id, search, supplier_id, order_status, date_from,
                date_to, limit, offset):
    if date_from and date_to and date_from > date_to:
        raise HTTPException(status_code=422, detail="Start date must be before end date.")
    with database_connection() as connection, database_cursor(connection) as cursor:
        rows, total = repository.list_company_orders(
            cursor, company_id, search.strip(), supplier_id, order_status,
            date_from, date_to, limit, offset,
        )
    items = []
    for row in rows:
        value = repository.serialize_order(row[:14])
        value["item_count"] = row[14]
        items.append(value)
    return {"items": items, "total": total, "limit": limit, "offset": offset}


def order_form_options(company_id):
    with database_connection() as connection, database_cursor(connection) as cursor:
        suppliers, products = repository.list_order_form_options(cursor, company_id)
    return {
        "suppliers": [{"supplier_id": r[0], "supplier_code": r[1], "supplier_name": r[2], "supplier_status": r[3]} for r in suppliers],
        "products": [{"product_id": r[0], "sku": r[1], "product_name": r[2],
                      "product_type": r[3], "variant_design": r[4], "variant_size": r[5],
                      "variant_color": r[6], "unit_code": r[7]} for r in products],
    }


def get_order(company_id, purchase_order_id):
    with database_connection() as connection, database_cursor(connection) as cursor:
        row = repository.get_company_order(cursor, company_id, purchase_order_id)
        if not row:
            raise HTTPException(status_code=404, detail="Purchase order not found.")
        return _serialize_detail(cursor, company_id, row)


def create_draft(company_id, user_id, payload: PurchaseOrderDraft):
    with database_connection() as connection, database_cursor(connection) as cursor:
        _ensure_supplier(cursor, company_id, payload.supplier_id)
        items, subtotal = _prepare_items(cursor, company_id, payload.items)
        sequence = repository.next_order_number_value(cursor)
        number = f"PO-{payload.order_date.year}-{sequence:06d}"
        try:
            order_id = repository.insert_order(
                cursor, number=number, company_id=company_id,
                supplier_id=payload.supplier_id, order_date=payload.order_date,
                expected_delivery_date=payload.expected_delivery_date,
                subtotal=subtotal, notes=payload.notes, created_by_user_id=user_id,
            )
            for item in items:
                repository.insert_order_item(
                    cursor, company_id=company_id, purchase_order_id=order_id, **item
                )
            repository.add_status_history(cursor, company_id, order_id, "DRAFT", user_id)
            row = repository.get_company_order(cursor, company_id, order_id)
            result = _serialize_detail(cursor, company_id, row)
            connection.commit()
        except pyodbc.IntegrityError as exc:
            if "2601" in str(exc) or "2627" in str(exc):
                raise HTTPException(status_code=409, detail="Purchase order number conflict. Retry the request.") from exc
            raise HTTPException(status_code=500, detail="Could not save the purchase order.") from exc
    return result


def update_draft(company_id, purchase_order_id, payload: PurchaseOrderDraft):
    with database_connection() as connection, database_cursor(connection) as cursor:
        existing = repository.get_company_order(cursor, company_id, purchase_order_id, lock=True)
        if not existing:
            raise HTTPException(status_code=404, detail="Purchase order not found.")
        if existing[6] != "DRAFT":
            raise HTTPException(status_code=409, detail="Only draft purchase orders can be edited.")
        _ensure_supplier(cursor, company_id, payload.supplier_id)
        items, subtotal = _prepare_items(cursor, company_id, payload.items)
        updated = repository.update_draft_order(
            cursor, company_id=company_id, purchase_order_id=purchase_order_id,
            supplier_id=payload.supplier_id, order_date=payload.order_date,
            expected_delivery_date=payload.expected_delivery_date,
            subtotal=subtotal, notes=payload.notes,
        )
        if updated.rowcount != 1:
            raise HTTPException(status_code=409, detail="This purchase order changed; reload and try again.")
        repository.replace_order_items(cursor, company_id, purchase_order_id, items)
        row = repository.get_company_order(cursor, company_id, purchase_order_id)
        result = _serialize_detail(cursor, company_id, row)
        connection.commit()
    return result


def _transition(company_id, user_id, purchase_order_id, target, note=None):
    allowed_from = {"SUBMITTED": "DRAFT", "CANCELLED": ("DRAFT", "SUBMITTED")}
    sources = allowed_from[target]
    if isinstance(sources, str):
        sources = (sources,)
    with database_connection() as connection, database_cursor(connection) as cursor:
        row = repository.get_company_order(cursor, company_id, purchase_order_id, lock=True)
        if not row:
            raise HTTPException(status_code=404, detail="Purchase order not found.")
        if row[6] not in sources:
            raise HTTPException(status_code=409, detail=f"A {row[6].lower()} purchase order cannot be {target.lower()}.")
        updated = repository.transition_order(cursor, company_id, purchase_order_id, row[6], target)
        if updated.rowcount != 1:
            raise HTTPException(status_code=409, detail="This purchase order changed; reload and try again.")
        repository.add_status_history(cursor, company_id, purchase_order_id, target, user_id, note)
        result_row = repository.get_company_order(cursor, company_id, purchase_order_id)
        result = _serialize_detail(cursor, company_id, result_row)
        connection.commit()
    return result


def submit_order(company_id, user_id, purchase_order_id):
    return _transition(company_id, user_id, purchase_order_id, "SUBMITTED")


def cancel_order(company_id, user_id, purchase_order_id, note=None):
    return _transition(company_id, user_id, purchase_order_id, "CANCELLED", note)
