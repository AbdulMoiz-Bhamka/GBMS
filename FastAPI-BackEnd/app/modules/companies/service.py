import pyodbc
from fastapi import HTTPException

from app.db.connection import database_connection, database_cursor
from app.modules.companies import repository
from app.modules.companies.schemas import CompanyCreate, CompanyStatusUpdate, CompanyUpdate


def _integrity_error(exc, entity):
    message = str(exc)
    if "2601" in message or "2627" in message:
        raise HTTPException(
            status_code=409, detail=f"A {entity} with that name or code already exists."
        ) from exc
    raise HTTPException(
        status_code=500, detail=f"Could not save the {entity}. Please try again."
    ) from exc


def list_companies(search, limit, offset):
    with database_connection() as connection, database_cursor(connection) as cursor:
        rows, total = repository.list_companies(cursor, search.strip(), limit, offset)
    return {
        "items": [repository.serialize_company(row) for row in rows],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


def create_company(payload: CompanyCreate):
    with database_connection() as connection, database_cursor(connection) as cursor:
        try:
            row = repository.create_company(cursor, payload)
            connection.commit()
        except pyodbc.IntegrityError as exc:
            _integrity_error(exc, "company")
    return repository.serialize_company(row)


def get_company(company_id):
    with database_connection() as connection, database_cursor(connection) as cursor:
        row = repository.get_company(cursor, company_id)
    if not row:
        raise HTTPException(status_code=404, detail="Company not found.")
    return repository.serialize_company(row)


def update_company(company_id, payload: CompanyUpdate):
    values = payload.model_dump(exclude_unset=True)
    if not values:
        raise HTTPException(status_code=400, detail="Provide at least one company field to update.")
    if any(values.get(key) is None for key in ("company_name", "company_code") if key in values):
        raise HTTPException(status_code=422, detail="Company name and code cannot be empty.")
    with database_connection() as connection, database_cursor(connection) as cursor:
        try:
            row = repository.update_company(cursor, company_id, values)
            if not row:
                raise HTTPException(status_code=404, detail="Company not found.")
            connection.commit()
        except pyodbc.IntegrityError as exc:
            _integrity_error(exc, "company")
    return repository.serialize_company(row)


def set_company_status(company_id, payload: CompanyStatusUpdate):
    with database_connection() as connection, database_cursor(connection) as cursor:
        row = repository.update_company_status(cursor, company_id, payload.company_status)
        if not row:
            raise HTTPException(status_code=404, detail="Company not found.")
        connection.commit()
    return repository.serialize_company(row)
