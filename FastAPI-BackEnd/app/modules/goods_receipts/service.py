"""PO-linked receipts create identifiable lots and stock ledger entries atomically."""
import base64
import secrets
from decimal import Decimal
from uuid import uuid4

import barcode
import pyodbc
from barcode.writer import SVGWriter
from fastapi import HTTPException

from app.db.connection import database_connection, database_cursor
from app.modules.goods_receipts import repository
from app.modules.inventory import repository as inventory_repository


def _lot_number(company_id, receipt_id, line_number):
    return f"LOT-{company_id:04d}-{receipt_id:08d}-{line_number:03d}"


def create_receipt(company_id, actor_id, payload):
    with database_connection() as connection, database_cursor(connection) as cursor:
        prior = repository.get_receipt_by_key(cursor, company_id, payload.idempotency_key)
        if prior:
            header, lines = repository.receipt_details(cursor, company_id, prior[0])
            return serialize_receipt(header, lines, already_processed=True)
        order = repository.get_order_for_update(cursor, company_id, payload.purchase_order_id)
        if not order:
            raise HTTPException(404, "Purchase order not found for this company.")
        supplier_id, order_status, _po_number = order
        if order_status not in {"SUBMITTED", "PARTIALLY_RECEIVED"}:
            raise HTTPException(409, "Only submitted or partially received purchase orders can receive goods.")
        receipt_number = f"GR-{company_id:04d}-{uuid4().hex[:12].upper()}"
        try:
            receipt_id = repository.create_receipt(
                cursor, company_id, receipt_number, supplier_id, payload.purchase_order_id,
                actor_id, payload.notes, payload.idempotency_key,
            )
            for index, item in enumerate(payload.items, start=1):
                po_line = repository.get_order_line(
                    cursor, company_id, payload.purchase_order_id, item.purchase_order_item_id
                )
                if not po_line or po_line[0] != item.product_id:
                    raise HTTPException(422, "Each receipt item must match a product line on the selected purchase order.")
                product = repository.get_product_for_update(cursor, company_id, item.product_id)
                if not product or product[0] != "RAW_MATERIAL" or not product[2]:
                    raise HTTPException(422, "Goods receipts can only increase active raw-material products in this company.")
                already_received = Decimal(repository.received_for_line(cursor, company_id, item.purchase_order_item_id))
                if already_received + item.received_quantity > Decimal(po_line[1]):
                    raise HTTPException(422, "Received quantity exceeds the outstanding quantity on the purchase order line.")
                lot_number = item.lot_number or _lot_number(company_id, receipt_id, index)
                lot_id = repository.create_lot(
                    cursor, company_id, item.product_id, receipt_id, lot_number, item.received_quantity
                )
                repository.create_receipt_item(
                    cursor, company_id, receipt_id, payload.purchase_order_id,
                    item.product_id, item.purchase_order_item_id, lot_id,
                    item.received_quantity, item.unit_cost if item.unit_cost is not None else po_line[2],
                )
                previous = Decimal(product[1])
                new_balance = previous + item.received_quantity
                changed = inventory_repository.update_stock_balance(
                    cursor, company_id, item.product_id, previous, new_balance
                )
                if changed.rowcount != 1:
                    raise HTTPException(409, "Stock changed concurrently. Reload the order and retry.")
                inventory_repository.insert_inventory_transaction(
                    cursor, company_id=company_id, product_id=item.product_id,
                    transaction_type="GOODS_RECEIPT", quantity_changed=item.received_quantity,
                    previous_balance=previous, new_balance=new_balance, supplier_id=supplier_id,
                    purchase_order_id=payload.purchase_order_id, reference_number=receipt_number,
                    created_by_user_id=actor_id, notes=item.notes or payload.notes,
                    idempotency_key=uuid4(), material_lot_id=lot_id, goods_receipt_id=receipt_id,
                )
                barcode_value = f"GBMS{company_id:06X}LOT{secrets.token_hex(8).upper()}"
                repository.insert_barcode(cursor, company_id, barcode_value, lot_id, actor_id)

            refreshed_lines = repository.list_order_lines(cursor, company_id, payload.purchase_order_id)
            # row[11] = total received so far, row[8] = ordered quantity
            completed = all(Decimal(str(row[11])) >= Decimal(str(row[8])) for row in refreshed_lines)
            next_status = "COMPLETED" if completed else "PARTIALLY_RECEIVED"
            if next_status != order_status:
                cursor.execute(
                    "UPDATE dbo.PurchaseOrders SET Status=?,UpdatedAt=SYSUTCDATETIME() WHERE CompanyID=? AND PurchaseOrderID=?",
                    next_status, company_id, payload.purchase_order_id,
                )
                cursor.execute(
                    """INSERT INTO dbo.PurchaseOrderStatusHistory
                       (CompanyID,PurchaseOrderID,Status,ChangedByUserID,Note)
                       VALUES(?,?,?,?,?)""", company_id, payload.purchase_order_id,
                    next_status, actor_id, f"Updated automatically when goods receipt {receipt_number} was posted.",
                )
            header, lines = repository.receipt_details(cursor, company_id, receipt_id)
            connection.commit()
        except HTTPException:
            raise
        except pyodbc.IntegrityError as exc:
            raise HTTPException(409, "Receipt or lot reference already exists. Check your entries and retry.") from exc
    return serialize_receipt(header, lines)


def serialize_receipt(header, lines, already_processed=False):
    return {
        "goods_receipt_id": header[0], "receipt_number": header[1],
        "supplier_id": header[2], "supplier_name": header[3],
        "purchase_order_id": header[4], "purchase_order_number": header[5],
        "received_at": header[6], "created_by_user_id": header[7],
        "created_by_name": header[8], "notes": header[9],
        "already_processed": already_processed,
        "items": [{"receipt_item_id": r[0], "product_id": r[1], "sku": r[2],
                   "product_name": r[3], "purchase_order_item_id": r[4],
                   "material_lot_id": r[5], "lot_number": r[6],
                   "received_quantity": r[7], "unit_code": r[8], "unit_cost": r[9]}
                  for r in lines],
    }


def receipt_options(company_id, purchase_order_id):
    with database_connection() as connection, database_cursor(connection) as cursor:
        try:
            orders = repository.list_open_orders(cursor, company_id)
        except pyodbc.ProgrammingError as exc:
            if "Invalid object name" in str(exc) or "42S02" in str(exc):
                raise HTTPException(
                    status_code=503,
                    detail=(
                        "The goods receipt tables are not available. "
                        "Run the full GBMS_DB.sql migration script in SSMS to create them."
                    ),
                ) from exc
            raise
        if purchase_order_id is None:
            return {"purchase_orders": [serialize_order_option(row) for row in orders], "items": []}
        order = repository.get_order_for_update(cursor, company_id, purchase_order_id)
        if not order:
            raise HTTPException(404, "Purchase order not found for this company.")
        rows = repository.list_order_lines(cursor, company_id, purchase_order_id)
    return {"purchase_orders": [serialize_order_option(row) for row in orders],
            "items": [{"purchase_order_item_id": r[0], "product_id": r[1], "sku": r[2],
                       "product_name": r[3], "design": r[4], "size": r[5], "color": r[6],
                       "unit_code": r[7], "ordered_quantity": r[8], "unit_cost": r[9],
                       "product_type": r[10], "received_quantity": r[11], "outstanding_quantity": max(Decimal(r[8])-Decimal(r[11]), Decimal(0))}
                      for r in rows]}


def serialize_order_option(row):
    return {"purchase_order_id": row[0], "purchase_order_number": row[1],
            "supplier_id": row[2], "supplier_name": row[3], "status": row[4],
            "order_date": row[5], "line_count": row[6]}


def list_material_lots(company_id, product_id=None):
    with database_connection() as connection, database_cursor(connection) as cursor:
        try:
            rows = repository.list_lots(cursor, company_id, product_id)
        except pyodbc.ProgrammingError as exc:
            # Raised when the manufacturing tables don't exist yet (migration not applied).
            if "Invalid object name" in str(exc) or "42S02" in str(exc):
                raise HTTPException(
                    status_code=503,
                    detail=(
                        "The goods receipt tables are not available. "
                        "Run the full GBMS_DB.sql migration script in SSMS to create them."
                    ),
                ) from exc
            raise
    return [{"material_lot_id": r[0], "product_id": r[1], "sku": r[2], "product_name": r[3],
             "goods_receipt_id": r[4], "receipt_number": r[5], "purchase_order_id": r[6],
             "purchase_order_number": r[7], "supplier_id": r[8], "supplier_name": r[9],
             "lot_number": r[10], "original_quantity": r[11], "remaining_quantity": r[12],
             "unit_code": r[13], "created_at": r[14]} for r in rows]


def barcode_label(company_id, lot_id):
    with database_connection() as connection, database_cursor(connection) as cursor:
        row = repository.get_lot_barcode_record(cursor, company_id, lot_id)
    if not row:
        raise HTTPException(404, "Material lot barcode was not found for this company.")
    svg = barcode.get("code128", row[0], writer=SVGWriter()).render(
        writer_options={"module_width": 0.28, "module_height": 18, "quiet_zone": 4,
                       "font_size": 9, "text_distance": 2, "background": "white", "foreground": "black"}
    )
    return {"barcode_value": row[0], "material_lot_id": row[1], "lot_number": row[2],
            "product_id": row[3], "sku": row[4], "product_name": row[5],
            "supplier_name": row[6], "purchase_order_number": row[7], "receipt_number": row[8],
            "original_quantity": row[9], "remaining_quantity": row[10], "unit_code": row[11],
            "company_name": row[12], "barcode_svg_base64": base64.b64encode(svg).decode("ascii")}


def lookup_barcode(company_id, value):
    with database_connection() as connection, database_cursor(connection) as cursor:
        entity = repository.get_barcode_entity(cursor, company_id, value)
        if not entity:
            raise HTTPException(404, "Barcode not found for this company.")
        if entity[0] != "MATERIAL_LOT":
            return {"entity_type": entity[0], "product_id": entity[1], "material_lot_id": entity[2],
                    "production_batch_id": entity[3], "bundle_id": entity[4]}
        row = repository.get_lot_barcode_record(cursor, company_id, entity[2])
    label = barcode_label(company_id, entity[2])
    label.update({"entity_type": entity[0], "original_quantity": row[9], "remaining_quantity": row[10]})
    return label
