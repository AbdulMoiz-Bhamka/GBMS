# app/db/connection.py
"""SQL Server connection lifecycle and cursor helpers."""

from contextlib import contextmanager
import logging
import sys

import pyodbc
from fastapi import HTTPException

from app.core.config import DB_DRIVER, DB_NAME, DB_PASSWORD, DB_PORT, DB_SERVER, DB_USER

logger = logging.getLogger("gbms.database")


def get_connection():
    if not DB_SERVER:
        raise HTTPException(
            status_code=503,
            detail="Set DB_SERVER to the externally reachable SQL Server host in the deployment environment.",
        )
    db_user = DB_USER.strip()
    db_password = DB_PASSWORD
    has_password = bool(db_password.strip())
    if bool(db_user) != has_password:
        raise HTTPException(
            status_code=503,
            detail="Configure both DB_USER and DB_PASSWORD, or leave both blank for local Windows authentication.",
        )
    if db_user and has_password:
        auth = f"UID={db_user};PWD={db_password};"
    elif sys.platform == "win32":
        auth = "Trusted_Connection=yes;"
    else:
        raise HTTPException(
            status_code=503,
            detail="Hosted deployments require SQL Server credentials in DB_USER and DB_PASSWORD.",
        )
    server = f"tcp:{DB_SERVER},{DB_PORT}" if DB_PORT else DB_SERVER
    connection_string = (
        f"DRIVER={{{DB_DRIVER}}};SERVER={server};DATABASE={DB_NAME};"
        f"{auth}TrustServerCertificate=yes;"
    )
    try:
        return pyodbc.connect(connection_string, timeout=5)
    except pyodbc.Error as exc:
        logger.exception(
            "SQL Server connection failed (server=%s, port=%s, database=%s, driver=%s).",
            DB_SERVER,
            DB_PORT or "instance discovery",
            DB_NAME,
            DB_DRIVER,
        )
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
