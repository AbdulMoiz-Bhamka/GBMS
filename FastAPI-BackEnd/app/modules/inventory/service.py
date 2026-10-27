import base64
import secrets

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


def list_products(company_id, search, category_id, limit, offset):
    with database_connection() as connection, database_cursor(connection) as cursor:
        rows, total = repository.list_products(
            cursor, company_id, search.strip(), category_id, limit, offset
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


def create_product(company_id, payload: ProductCreate):
    if payload.product_type == "RAW_MATERIAL" and payload.selling_price is not None:
        raise HTTPException(status_code=422, detail="Selling price is only available for finished goods.")
    with database_connection() as connection, database_cursor(connection) as cursor:
        _ensure_category(cursor, payload.category_id, company_id)
        _ensure_unit(cursor, payload.unit_id)
        try:
            product_id = repository.insert_product(cursor, company_id, payload)
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
    non_nullable = {"sku", "product_name", "product_type", "unit_id", "quantity_on_hand", "reorder_level"}
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


def generate_product_barcode(company_id, product_id):
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
                result = repository.set_product_barcode(cursor, company_id, product_id, value)
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
