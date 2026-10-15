import pyodbc
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
    non_nullable = {"sku", "product_name", "product_type", "unit_id", "reorder_level"}
    if any(values.get(key) is None for key in non_nullable if key in values):
        raise HTTPException(status_code=422, detail="Required product fields cannot be empty.")
    with database_connection() as connection, database_cursor(connection) as cursor:
        _get_company_product(cursor, company_id, product_id)
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
