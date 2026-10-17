# app/db/connection.py
"""SQL Server connection lifecycle and cursor helpers."""

from contextlib import contextmanager

import pyodbc
from fastapi import HTTPException

from app.core.config import DB_DRIVER, DB_NAME, DB_PASSWORD, DB_SERVER, DB_USER


def get_connection():
    if DB_USER and DB_PASSWORD:
        auth = f"UID={DB_USER};PWD={DB_PASSWORD};"
    else:
        auth = "Trusted_Connection=yes;"
    connection_string = (
        f"DRIVER={{{DB_DRIVER}}};SERVER={DB_SERVER};DATABASE={DB_NAME};"
        f"{auth}TrustServerCertificate=yes;"
    )
    try:
        return pyodbc.connect(connection_string, timeout=5)
    except pyodbc.Error as exc:
        raise HTTPException(
            status_code=503,
            detail="Database is unavailable. Check the GBMS database connection settings.",
        ) from exc


@contextmanager
def database_connection():
    connection = get_connection()
    try:
        yield connection
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


@contextmanager
def database_cursor(connection):
    cursor = connection.cursor()
    try:
        yield cursor
    finally:
        cursor.close()
