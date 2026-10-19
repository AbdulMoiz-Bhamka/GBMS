# GBMS Phase 3.1 — Supplier Management

## Data and company isolation

Supplier records are stored in `dbo.Suppliers` in the existing `GBMS` database. Each supplier has a `CompanyID` foreign key; `(CompanyID, SupplierCode)` is unique, and `(CompanyID, SupplierID)` is indexed uniquely for safe company-scoped references in future purchasing tables. Suppliers include contact and business details, optional tax registration and payment terms, `ACTIVE`/`INACTIVE` status, and UTC creation/update timestamps.

The API does not accept `CompanyID` in supplier request bodies. It takes the company from the authenticated JWT user's database assignment and includes that company in every supplier read and write query. A supplier belonging to another company is returned as not found.

## API

All routes use `/api/v1/suppliers`:

- `GET /api/v1/suppliers?search=&supplier_status=&limit=25&offset=0` — search and filter the signed-in company's suppliers.
- `POST /api/v1/suppliers` — create a supplier.
- `GET /api/v1/suppliers/{supplier_id}` — view supplier details.
- `PUT /api/v1/suppliers/{supplier_id}` — update supplier details.
- `PATCH /api/v1/suppliers/{supplier_id}/status` — activate or deactivate a supplier.

Permissions are `suppliers.view`, `suppliers.create`, `suppliers.update`, and `suppliers.deactivate`. The current unconfigured COMPANY_ADMIN defaults include these permissions. Other company users receive only permissions selected by their administrator. Super Admin does not have company context in these operational routes.

## Code map

- `FastAPI-BackEnd/app/modules/suppliers/schemas.py` — request validation and normalization.
- `FastAPI-BackEnd/app/modules/suppliers/repository.py` — parameterized SQL Server queries with company scope.
- `FastAPI-BackEnd/app/modules/suppliers/service.py` — transactions, duplicate-code handling, and not-found behavior.
- `FastAPI-BackEnd/app/modules/suppliers/router.py` — authenticated API endpoints and permission dependencies.
- `FastAPI-BackEnd/app/core/permissions.py` — permission catalog and default COMPANY_ADMIN access.
- `FastAPI-BackEnd/app/main.py` — module registration.
- `React (FrontEnd)/GBMS/src/pages/Suppliers/SuppliersPage.jsx` — searchable, paginated supplier list, forms, status controls, and details dialog.
- `React (FrontEnd)/GBMS/src/services/supplierService.js` — frontend API calls.
- `React (FrontEnd)/GBMS/src/App.jsx` and `src/Components/Layout/Sidebar.jsx` — protected route and permission-gated navigation.
- `SQL Server Query/GBMS_DB.sql` — additive, repeatable supplier table/index and permission-catalog migration.

Supplier operations do not create purchase orders or change inventory quantities. Those workflows belong to the later Phase 3 milestones.

## Migration and verification

The migration is included in `SQL Server Query/GBMS_DB.sql` and was not executed against SQL Server. Run the script in SQL Server Management Studio before using the supplier API; it adds the new table and permission catalog rows without dropping existing tables or records.

The automated database-free suite covers supplier request validation, list/detail tenant predicates, create/update/status service behavior, duplicate-code conflicts, and registered routes. These checks do not replace a live SQL Server integration test after migration.
