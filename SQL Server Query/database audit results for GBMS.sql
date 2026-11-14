/* 1. Identity of this SSMS connection and database */
SELECT
    @@SERVERNAME AS ServerName,
    DB_NAME() AS DatabaseName,
    ORIGINAL_LOGIN() AS OriginalLogin,
    SUSER_SNAME() AS CurrentLogin,
    c.auth_scheme AS AuthScheme
FROM sys.dm_exec_connections AS c
WHERE c.session_id = @@SPID;


/* Tables requested for the traceability review */
WITH RequestedTables AS
(
    SELECT TableName
    FROM (VALUES
        (N'MaterialLots'),
        (N'BarcodeRegistry'),
        (N'ProductionWorkOrders'),
        (N'ProductionBatches'),
        (N'ProductionMaterialConsumptions'),
        (N'ProductionStageHistory'),
        (N'ProductionBundles'),
        (N'QualityInspections'),
        (N'FinishedGoodsRegistrations'),
        (N'FinishedGoodMaterialComponents'),
        (N'Products'),
        (N'InventoryTransactions'),
        (N'GoodsReceipts'),
        (N'GoodsReceiptItems'),
        (N'PurchaseOrders'),
        (N'PurchaseOrderItems'),
        (N'Suppliers')
    ) AS v(TableName)
)
SELECT
    r.TableName,
    CASE WHEN t.object_id IS NULL THEN N'MISSING' ELSE N'EXISTS' END AS TableStatus
FROM RequestedTables AS r
LEFT JOIN sys.tables AS t
    ON t.name = r.TableName
   AND SCHEMA_NAME(t.schema_id) = N'dbo'
ORDER BY r.TableName;


/* 2. Columns and SQL types */
SELECT
    s.name AS SchemaName,
    t.name AS TableName,
    c.column_id AS ColumnOrdinal,
    c.name AS ColumnName,
    TYPE_NAME(c.user_type_id) AS DataType,
    CASE
        WHEN TYPE_NAME(c.user_type_id) IN (N'nvarchar', N'nchar', N'varchar', N'char',
                                           N'varbinary', N'binary')
            THEN c.max_length
        ELSE NULL
    END AS MaxLengthBytes,
    c.precision AS NumericPrecision,
    c.scale AS NumericScale,
    c.is_nullable AS IsNullable,
    dc.definition AS DefaultDefinition,
    c.is_identity AS IsIdentity
FROM sys.tables AS t
JOIN sys.schemas AS s ON s.schema_id = t.schema_id
JOIN sys.columns AS c ON c.object_id = t.object_id
LEFT JOIN sys.default_constraints AS dc
    ON dc.parent_object_id = c.object_id
   AND dc.parent_column_id = c.column_id
WHERE s.name = N'dbo'
  AND t.name IN (
      N'MaterialLots', N'BarcodeRegistry', N'ProductionWorkOrders',
      N'ProductionBatches', N'ProductionMaterialConsumptions',
      N'ProductionStageHistory', N'ProductionBundles', N'QualityInspections',
      N'FinishedGoodsRegistrations', N'FinishedGoodMaterialComponents',
      N'Products', N'InventoryTransactions', N'GoodsReceipts',
      N'GoodsReceiptItems', N'PurchaseOrders', N'PurchaseOrderItems',
      N'Suppliers'
  )
ORDER BY t.name, c.column_id;


/* 3. Primary keys, unique constraints/indexes, and index columns */
SELECT
    s.name AS SchemaName,
    t.name AS TableName,
    i.name AS IndexName,
    i.is_primary_key AS IsPrimaryKey,
    i.is_unique AS IsUnique,
    i.is_unique_constraint AS IsUniqueConstraint,
    i.type_desc AS IndexType,
    i.has_filter AS HasFilter,
    i.filter_definition AS FilterDefinition,
    ic.key_ordinal AS KeyOrdinal,
    ic.is_included_column AS IsIncludedColumn,
    c.name AS ColumnName,
    ic.is_descending_key AS IsDescending
FROM sys.tables AS t
JOIN sys.schemas AS s ON s.schema_id = t.schema_id
JOIN sys.indexes AS i ON i.object_id = t.object_id
JOIN sys.index_columns AS ic
    ON ic.object_id = i.object_id
   AND ic.index_id = i.index_id
JOIN sys.columns AS c
    ON c.object_id = ic.object_id
   AND c.column_id = ic.column_id
WHERE s.name = N'dbo'
  AND t.name IN (
      N'MaterialLots', N'BarcodeRegistry', N'ProductionWorkOrders',
      N'ProductionBatches', N'ProductionMaterialConsumptions',
      N'ProductionStageHistory', N'ProductionBundles', N'QualityInspections',
      N'FinishedGoodsRegistrations', N'FinishedGoodMaterialComponents',
      N'Products', N'InventoryTransactions', N'GoodsReceipts',
      N'GoodsReceiptItems', N'PurchaseOrders', N'PurchaseOrderItems',
      N'Suppliers'
  )
  AND i.is_hypothetical = 0
ORDER BY t.name, i.name, ic.key_ordinal, ic.index_column_id;


/* 4. Foreign keys, including every column in composite keys */
SELECT
    fk.name AS ForeignKeyName,
    ps.name AS ParentSchema,
    pt.name AS ParentTable,
    pc.name AS ParentColumn,
    rs.name AS ReferencedSchema,
    rt.name AS ReferencedTable,
    rc.name AS ReferencedColumn,
    fkc.constraint_column_id AS ColumnPairOrdinal,
    fk.delete_referential_action_desc AS OnDelete,
    fk.update_referential_action_desc AS OnUpdate,
    fk.is_disabled AS IsDisabled,
    fk.is_not_trusted AS IsNotTrusted
FROM sys.foreign_keys AS fk
JOIN sys.foreign_key_columns AS fkc
    ON fkc.constraint_object_id = fk.object_id
JOIN sys.tables AS pt ON pt.object_id = fk.parent_object_id
JOIN sys.schemas AS ps ON ps.schema_id = pt.schema_id
JOIN sys.columns AS pc
    ON pc.object_id = fkc.parent_object_id
   AND pc.column_id = fkc.parent_column_id
JOIN sys.tables AS rt ON rt.object_id = fk.referenced_object_id
JOIN sys.schemas AS rs ON rs.schema_id = rt.schema_id
JOIN sys.columns AS rc
    ON rc.object_id = fkc.referenced_object_id
   AND rc.column_id = fkc.referenced_column_id
WHERE ps.name = N'dbo'
  AND (
      pt.name IN (
          N'MaterialLots', N'BarcodeRegistry', N'ProductionWorkOrders',
          N'ProductionBatches', N'ProductionMaterialConsumptions',
          N'ProductionStageHistory', N'ProductionBundles', N'QualityInspections',
          N'FinishedGoodsRegistrations', N'FinishedGoodMaterialComponents',
          N'Products', N'InventoryTransactions', N'GoodsReceipts',
          N'GoodsReceiptItems', N'PurchaseOrders', N'PurchaseOrderItems',
          N'Suppliers'
      )
      OR rt.name IN (
          N'MaterialLots', N'BarcodeRegistry', N'ProductionWorkOrders',
          N'ProductionBatches', N'ProductionMaterialConsumptions',
          N'ProductionStageHistory', N'ProductionBundles', N'QualityInspections',
          N'FinishedGoodsRegistrations', N'FinishedGoodMaterialComponents',
          N'Products', N'InventoryTransactions', N'GoodsReceipts',
          N'GoodsReceiptItems', N'PurchaseOrders', N'PurchaseOrderItems',
          N'Suppliers'
      )
  )
ORDER BY pt.name, fk.name, fkc.constraint_column_id;


/* 5. Check constraints */
SELECT
    s.name AS SchemaName,
    t.name AS TableName,
    cc.name AS ConstraintName,
    cc.definition AS CheckDefinition,
    cc.is_disabled AS IsDisabled,
    cc.is_not_trusted AS IsNotTrusted
FROM sys.check_constraints AS cc
JOIN sys.tables AS t ON t.object_id = cc.parent_object_id
JOIN sys.schemas AS s ON s.schema_id = t.schema_id
WHERE s.name = N'dbo'
  AND t.name IN (
      N'MaterialLots', N'BarcodeRegistry', N'ProductionWorkOrders',
      N'ProductionBatches', N'ProductionMaterialConsumptions',
      N'ProductionStageHistory', N'ProductionBundles', N'QualityInspections',
      N'FinishedGoodsRegistrations', N'FinishedGoodMaterialComponents',
      N'Products', N'InventoryTransactions', N'GoodsReceipts',
      N'GoodsReceiptItems', N'PurchaseOrders', N'PurchaseOrderItems',
      N'Suppliers'
  )
ORDER BY t.name, cc.name;


/* 6. Record counts only; no personal or sensitive values are returned.
   Existing requested tables are included; missing tables are skipped. */
DECLARE @countSql nvarchar(max);

SELECT @countSql =
    STUFF((
        SELECT
            N' UNION ALL SELECT N''' + REPLACE(t.name, N'''', N'''''') +
            N''' AS TableName, COUNT_BIG(*) AS RecordCount FROM ' +
            QUOTENAME(s.name) + N'.' + QUOTENAME(t.name)
        FROM sys.tables AS t
        JOIN sys.schemas AS s ON s.schema_id = t.schema_id
        WHERE s.name = N'dbo'
          AND t.name IN (
              N'MaterialLots', N'BarcodeRegistry', N'ProductionWorkOrders',
              N'ProductionBatches', N'ProductionMaterialConsumptions',
              N'ProductionStageHistory', N'ProductionBundles', N'QualityInspections',
              N'FinishedGoodsRegistrations', N'FinishedGoodMaterialComponents',
              N'Products', N'InventoryTransactions', N'GoodsReceipts',
              N'GoodsReceiptItems', N'PurchaseOrders', N'PurchaseOrderItems',
              N'Suppliers'
          )
        ORDER BY t.name
        FOR XML PATH(N''), TYPE
    ).value(N'.', N'nvarchar(max)'), 1, 11, N'');

IF @countSql IS NOT NULL AND LEN(@countSql) > 0
    EXEC sys.sp_executesql @countSql;