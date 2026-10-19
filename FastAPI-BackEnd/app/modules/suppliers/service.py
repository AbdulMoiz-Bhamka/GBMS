import pyodbc
from fastapi import HTTPException

from app.db.connection import database_connection, database_cursor
from app.modules.suppliers import repository
from app.modules.suppliers.schemas import SupplierCreate, SupplierUpdate


def _handle_integrity_error(exc):
    if "2601" in str(exc) or "2627" in str(exc):
        raise HTTPException(
            status_code=409,
            detail="A supplier with this code already exists in your company.",
        ) from exc
    raise HTTPException(
        status_code=500, detail="Could not save the supplier. Please try again."
    ) from exc


def list_suppliers(company_id, search, supplier_status, limit, offset):
    with database_connection() as connection, database_cursor(connection) as cursor:
        rows, total = repository.list_suppliers(
            cursor, company_id, search.strip(), supplier_status, limit, offset
        )
    return {
        "items": [repository.serialize_supplier(row) for row in rows],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


def get_supplier(company_id, supplier_id):
    with database_connection() as connection, database_cursor(connection) as cursor:
        row = repository.get_supplier(cursor, company_id, supplier_id)
    if not row:
        raise HTTPException(status_code=404, detail="Supplier not found.")
    return repository.serialize_supplier(row)


def create_supplier(company_id, payload: SupplierCreate):
    with database_connection() as connection, database_cursor(connection) as cursor:
        try:
            supplier_id = repository.insert_supplier(cursor, company_id, payload)
            row = repository.get_supplier(cursor, company_id, supplier_id)
            connection.commit()
        except pyodbc.IntegrityError as exc:
            _handle_integrity_error(exc)
    return repository.serialize_supplier(row)


def update_supplier(company_id, supplier_id, payload: SupplierUpdate):
    values = payload.model_dump(exclude_unset=True)
    if not values:
        raise HTTPException(status_code=400, detail="Provide at least one supplier field to update.")
    for field in ("supplier_code", "supplier_name"):
        if field in values and values[field] is None:
            raise HTTPException(status_code=422, detail=f"{field.replace('_', ' ').capitalize()} cannot be empty.")
    with database_connection() as connection, database_cursor(connection) as cursor:
        if not repository.get_supplier(cursor, company_id, supplier_id):
            raise HTTPException(status_code=404, detail="Supplier not found.")
        try:
            repository.update_supplier(cursor, company_id, supplier_id, values)
            row = repository.get_supplier(cursor, company_id, supplier_id)
            connection.commit()
        except pyodbc.IntegrityError as exc:
            _handle_integrity_error(exc)
    return repository.serialize_supplier(row)


def set_supplier_status(company_id, supplier_id, supplier_status):
    with database_connection() as connection, database_cursor(connection) as cursor:
        result = repository.update_supplier_status(
            cursor, company_id, supplier_id, supplier_status
        )
        if result.rowcount == 0:
            raise HTTPException(status_code=404, detail="Supplier not found.")
        row = repository.get_supplier(cursor, company_id, supplier_id)
        connection.commit()
    return repository.serialize_supplier(row)
