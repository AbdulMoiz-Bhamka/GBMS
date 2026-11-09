# GBMS manufacturing and traceability implementation

## Existing architecture findings

- React/Vite frontend and FastAPI/pyodbc backend already implement JWT, per-company authorization, products, suppliers, purchase orders, finished-good product barcodes, and product stock.
- `dbo.Products` is the existing product/variant catalogue. `QuantityOnHand` is company-scoped through `CompanyID`; do not create a parallel product table.
- `dbo.InventoryTransactions` is the stock ledger introduced in the inventory upgrade. Product balance writes must remain atomic with ledger writes.
- There is no goods receipt, material lot/package, production work order/batch, WIP bundle, QC, finished output, or genealogy implementation in the inspected project.
- Existing `dbo.FinishedGoodMaterialComponents` is a bill-of-materials relationship, not evidence of actual consumption or traceability.
- Existing product barcode values identify variants. Lot, package, bundle, and production batch barcodes need separate typed identifiers.
- SQL changes are consolidated in `SQL Server Query/GBMS_DB.sql`, per project convention. No SQL is executed by this implementation.

## Dependency plan and checklist

- [x] Inspect the existing project and document what is already present versus missing.
- [ ] Phase 1: add company-scoped receipt, lot, typed barcode, and production genealogy schema in the existing SQL file.
- [ ] Phase 2: split raw-material and finished-goods inventory navigation/views while reusing the existing Products and stock services.
- [ ] Phase 3: implement PO-linked partial goods receipts, material lots, lot barcode generation/printing, and receipt history.
- [ ] Phase 4: implement manual/keyboard and camera barcode lookup, then explicit authorized material issue.
- [ ] Phase 5: implement work orders, production batches, standard stages, bundles, quality inspection, packing, and finished output.
- [ ] Phase 6: implement forward/backward genealogy and centralized typed barcode lookup.
- [ ] Phase 7: integrate dashboard activity and verify authorization, idempotency, and tenant isolation end to end.

The phases remain unchecked until their code, tests, and schema are present. A schema-only foundation is not an implemented manufacturing workflow.
