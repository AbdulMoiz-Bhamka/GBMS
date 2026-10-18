"""Company-scoped overview service."""

from app.db.connection import database_connection, database_cursor
from app.modules.dashboard import repository


def company_overview(company_id):
    with database_connection() as connection, database_cursor(connection) as cursor:
        product_total = repository.product_count(cursor, company_id)
        product_rows = repository.inventory_chart(cursor, company_id)
        worker_row = repository.worker_counts(cursor, company_id)
        generated_at = repository.snapshot_time(cursor)

    total_workers = int(worker_row[0] or 0)
    active_workers = int(worker_row[1] or 0)
    return {
        "generated_at": generated_at,
        "revenue": {
            "amount": None,
            "currency": None,
            "status": "not_tracked",
            "message": "Sales records are not tracked yet.",
        },
        "inventory": {
            "active_product_count": int(product_total),
            "items": [
                {
                    "product_id": row[0],
                    "product_name": row[1],
                    "quantity": float(row[2]),
                    "unit": row[3],
                }
                for row in product_rows
            ],
        },
        "workers": {
            "total": total_workers,
            "active_accounts": active_workers,
            "inactive_accounts": total_workers - active_workers,
        },
    }
