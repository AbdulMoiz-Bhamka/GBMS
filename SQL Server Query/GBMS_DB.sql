/*
    GBMS_Database database setup
    Run this single script in SQL Server Management Studio.

    Safe to rerun: it creates missing schema objects and seeds missing roles,
    reference units, and other configured defaults without resetting existing data.
    It does not create users with passwords or display sensitive user records.
*/

-- 1. Create the GBMS_Database database and the original authentication tables.
IF DB_ID(N'GBMS_Database') IS NULL
    CREATE DATABASE [GBMS_Database];
GO

USE [GBMS_Database];
GO

IF OBJECT_ID(N'dbo.Roles', N'U') IS NULL
BEGIN
    CREATE TABLE dbo.Roles
    (
        RoleID INT IDENTITY(1,1) NOT NULL CONSTRAINT PK_Roles PRIMARY KEY,
        RoleName NVARCHAR(50) NOT NULL CONSTRAINT UQ_Roles_RoleName UNIQUE,
        Description NVARCHAR(250) NULL,
        CreatedAt DATETIME2(0) NOT NULL
            CONSTRAINT DF_Roles_CreatedAt DEFAULT SYSUTCDATETIME()
    );
END;
GO

IF OBJECT_ID(N'dbo.Users', N'U') IS NULL
BEGIN
    CREATE TABLE dbo.Users
    (
        UserID INT IDENTITY(1,1) NOT NULL CONSTRAINT PK_Users PRIMARY KEY,
        Username NVARCHAR(80) NOT NULL,
        FullName NVARCHAR(160) NOT NULL,
        Email NVARCHAR(254) NOT NULL,
        PasswordHash NVARCHAR(255) NOT NULL,
        RoleID INT NOT NULL,
        AccountStatus NVARCHAR(20) NOT NULL
            CONSTRAINT DF_Users_AccountStatus DEFAULT N'ACTIVE',
        CreatedAt DATETIME2(0) NOT NULL
            CONSTRAINT DF_Users_CreatedAt DEFAULT SYSUTCDATETIME(),
        UpdatedAt DATETIME2(0) NOT NULL
            CONSTRAINT DF_Users_UpdatedAt DEFAULT SYSUTCDATETIME(),
        CONSTRAINT FK_Users_Roles FOREIGN KEY (RoleID)
            REFERENCES dbo.Roles(RoleID),
        CONSTRAINT CK_Users_AccountStatus CHECK
            (AccountStatus IN (N'ACTIVE', N'INACTIVE', N'SUSPENDED'))
    );
END;
GO

IF NOT EXISTS (
    SELECT 1 FROM sys.indexes
    WHERE object_id = OBJECT_ID(N'dbo.Users')
      AND name = N'UQ_Users_Username'
)
    CREATE UNIQUE INDEX UQ_Users_Username ON dbo.Users(Username);
GO

IF NOT EXISTS (
    SELECT 1 FROM sys.indexes
    WHERE object_id = OBJECT_ID(N'dbo.Users')
      AND name = N'UQ_Users_Email'
)
    CREATE UNIQUE INDEX UQ_Users_Email ON dbo.Users(Email);
GO

IF NOT EXISTS (SELECT 1 FROM dbo.Roles WHERE RoleName = N'SUPER_ADMIN')
    INSERT INTO dbo.Roles (RoleName, Description)
    VALUES (N'SUPER_ADMIN', N'Full access to the GBMS_Database workspace');
GO

GO

-- 2. Add multi-company and inventory schema and seed missing company roles.
/*
   GBMS_Database multi-company and inventory foundation.
   Additive and repeatable: existing Roles, Users, password hashes, and
   other records are preserved. Run in SQL Server Management Studio or
   sqlcmd while connected to the GBMS_Database database.
*/
USE [GBMS_Database];
GO

IF OBJECT_ID(N'dbo.Companies', N'U') IS NULL
BEGIN
    CREATE TABLE dbo.Companies
    (
        CompanyID INT IDENTITY(1,1) NOT NULL CONSTRAINT PK_Companies PRIMARY KEY,
        CompanyName NVARCHAR(160) NOT NULL,
        CompanyCode NVARCHAR(30) NOT NULL,
        Email NVARCHAR(254) NULL,
        Phone NVARCHAR(40) NULL,
        Address NVARCHAR(400) NULL,
        CompanyStatus NVARCHAR(20) NOT NULL
            CONSTRAINT DF_Companies_CompanyStatus DEFAULT N'ACTIVE',
        CreatedAt DATETIME2(0) NOT NULL
            CONSTRAINT DF_Companies_CreatedAt DEFAULT SYSUTCDATETIME(),
        UpdatedAt DATETIME2(0) NOT NULL
            CONSTRAINT DF_Companies_UpdatedAt DEFAULT SYSUTCDATETIME(),
        CONSTRAINT CK_Companies_CompanyStatus
            CHECK (CompanyStatus IN (N'ACTIVE', N'INACTIVE')),
        CONSTRAINT CK_Companies_CompanyName_NotBlank
            CHECK (LEN(LTRIM(RTRIM(CompanyName))) > 0),
        CONSTRAINT CK_Companies_CompanyCode_NotBlank
            CHECK (LEN(LTRIM(RTRIM(CompanyCode))) > 0)
    );
END;
GO

IF NOT EXISTS (
    SELECT 1 FROM sys.indexes
    WHERE object_id = OBJECT_ID(N'dbo.Companies') AND name = N'UQ_Companies_CompanyCode'
)
    CREATE UNIQUE INDEX UQ_Companies_CompanyCode ON dbo.Companies(CompanyCode);
GO

IF NOT EXISTS (
    SELECT 1 FROM sys.indexes
    WHERE object_id = OBJECT_ID(N'dbo.Companies') AND name = N'UQ_Companies_CompanyName'
)
    CREATE UNIQUE INDEX UQ_Companies_CompanyName ON dbo.Companies(CompanyName);
GO

IF COL_LENGTH(N'dbo.Users', N'CompanyID') IS NULL
    ALTER TABLE dbo.Users ADD CompanyID INT NULL;
GO

IF NOT EXISTS (
    SELECT 1 FROM sys.foreign_keys
    WHERE parent_object_id = OBJECT_ID(N'dbo.Users') AND name = N'FK_Users_Companies'
)
    ALTER TABLE dbo.Users WITH CHECK
        ADD CONSTRAINT FK_Users_Companies FOREIGN KEY (CompanyID)
        REFERENCES dbo.Companies(CompanyID);
GO

IF NOT EXISTS (
    SELECT 1 FROM sys.indexes
    WHERE object_id = OBJECT_ID(N'dbo.Users') AND name = N'IX_Users_CompanyID'
)
    CREATE INDEX IX_Users_CompanyID ON dbo.Users(CompanyID);
GO

/* Roles stay global. Existing role and user IDs are never replaced. */
INSERT INTO dbo.Roles (RoleName, Description)
SELECT seed.RoleName, seed.Description
FROM (VALUES
    (N'COMPANY_ADMIN', N'Administrator for one assigned company'),
    (N'SUB_ADMIN', N'Company-scoped operational administrator'),
    (N'INVENTORY_USER', N'Company-scoped inventory user'),
    (N'WORKER', N'Factory worker with dashboard-only access')
) AS seed(RoleName, Description)
WHERE NOT EXISTS (SELECT 1 FROM dbo.Roles AS r WHERE r.RoleName = seed.RoleName);
GO

/* A single CompanyID enforces at most one tenant. The trigger enforces
   platform-vs-company role assignment for direct SQL account changes too. */
CREATE OR ALTER TRIGGER dbo.TR_Users_CompanyRoleScope
ON dbo.Users
AFTER INSERT, UPDATE
AS
BEGIN
    SET NOCOUNT ON;

    IF EXISTS
    (
        SELECT 1
        FROM inserted AS i
        INNER JOIN dbo.Roles AS r ON r.RoleID = i.RoleID
        WHERE (r.RoleName = N'SUPER_ADMIN' AND i.CompanyID IS NOT NULL)
           OR (r.RoleName <> N'SUPER_ADMIN' AND i.CompanyID IS NULL)
    )
        THROW 51001, 'SUPER_ADMIN must have no company; every other GBMS_Database role must have one company.', 1;
END;
GO

IF OBJECT_ID(N'dbo.UnitsOfMeasure', N'U') IS NULL
BEGIN
    CREATE TABLE dbo.UnitsOfMeasure
    (
        UnitID INT IDENTITY(1,1) NOT NULL CONSTRAINT PK_UnitsOfMeasure PRIMARY KEY,
        UnitCode NVARCHAR(16) NOT NULL,
        UnitName NVARCHAR(50) NOT NULL,
        Symbol NVARCHAR(16) NULL,
        IsActive BIT NOT NULL CONSTRAINT DF_UnitsOfMeasure_IsActive DEFAULT (1),
        CreatedAt DATETIME2(0) NOT NULL
            CONSTRAINT DF_UnitsOfMeasure_CreatedAt DEFAULT SYSUTCDATETIME(),
        CONSTRAINT UQ_UnitsOfMeasure_UnitCode UNIQUE (UnitCode),
        CONSTRAINT CK_UnitsOfMeasure_UnitCode_NotBlank
            CHECK (LEN(LTRIM(RTRIM(UnitCode))) > 0),
        CONSTRAINT CK_UnitsOfMeasure_UnitName_NotBlank
            CHECK (LEN(LTRIM(RTRIM(UnitName))) > 0)
    );
END;
GO

/* Units are global reference data shared by every company. */
INSERT INTO dbo.UnitsOfMeasure (UnitCode, UnitName, Symbol)
SELECT seed.UnitCode, seed.UnitName, seed.Symbol
FROM (VALUES
    (N'PC', N'Piece', N'pc'),
    (N'KG', N'Kilogram', N'kg'),
    (N'M', N'Metre', N'm'),
    (N'YD', N'Yard', N'yd'),
    (N'ROLL', N'Roll', N'roll'),
    (N'BOX', N'Box', N'box')
) AS seed(UnitCode, UnitName, Symbol)
WHERE NOT EXISTS
    (SELECT 1 FROM dbo.UnitsOfMeasure AS u WHERE u.UnitCode = seed.UnitCode);
GO

IF OBJECT_ID(N'dbo.ProductCategories', N'U') IS NULL
BEGIN
    CREATE TABLE dbo.ProductCategories
    (
        CategoryID INT IDENTITY(1,1) NOT NULL CONSTRAINT PK_ProductCategories PRIMARY KEY,
        CompanyID INT NOT NULL,
        CategoryName NVARCHAR(100) NOT NULL,
        Description NVARCHAR(300) NULL,
        CreatedAt DATETIME2(0) NOT NULL
            CONSTRAINT DF_ProductCategories_CreatedAt DEFAULT SYSUTCDATETIME(),
        UpdatedAt DATETIME2(0) NOT NULL
            CONSTRAINT DF_ProductCategories_UpdatedAt DEFAULT SYSUTCDATETIME(),
        CONSTRAINT FK_ProductCategories_Companies FOREIGN KEY (CompanyID)
            REFERENCES dbo.Companies(CompanyID),
        CONSTRAINT CK_ProductCategories_CategoryName_NotBlank
            CHECK (LEN(LTRIM(RTRIM(CategoryName))) > 0)
    );
END;
GO

IF NOT EXISTS (
    SELECT 1 FROM sys.indexes
    WHERE object_id = OBJECT_ID(N'dbo.ProductCategories')
      AND name = N'UQ_ProductCategories_Company_CategoryName'
)
    CREATE UNIQUE INDEX UQ_ProductCategories_Company_CategoryName
        ON dbo.ProductCategories(CompanyID, CategoryName);
GO

/* Composite unique key makes a cross-company category reference impossible. */
IF NOT EXISTS (
    SELECT 1 FROM sys.indexes
    WHERE object_id = OBJECT_ID(N'dbo.ProductCategories')
      AND name = N'UQ_ProductCategories_Company_CategoryID'
)
    CREATE UNIQUE INDEX UQ_ProductCategories_Company_CategoryID
        ON dbo.ProductCategories(CompanyID, CategoryID);
GO

IF OBJECT_ID(N'dbo.Products', N'U') IS NULL
BEGIN
    CREATE TABLE dbo.Products
    (
        ProductID INT IDENTITY(1,1) NOT NULL CONSTRAINT PK_Products PRIMARY KEY,
        CompanyID INT NOT NULL,
        CategoryID INT NULL,
        SKU NVARCHAR(60) NOT NULL,
        ProductName NVARCHAR(180) NOT NULL,
        ProductType NVARCHAR(24) NOT NULL,
        UnitID INT NOT NULL,
        Description NVARCHAR(1000) NULL,
        QuantityOnHand DECIMAL(18,3) NOT NULL
            CONSTRAINT DF_Products_QuantityOnHand DEFAULT (0),
        ReorderLevel DECIMAL(18,3) NOT NULL
            CONSTRAINT DF_Products_ReorderLevel DEFAULT (0),
        IsActive BIT NOT NULL CONSTRAINT DF_Products_IsActive DEFAULT (1),
        CreatedAt DATETIME2(0) NOT NULL
            CONSTRAINT DF_Products_CreatedAt DEFAULT SYSUTCDATETIME(),
        UpdatedAt DATETIME2(0) NOT NULL
            CONSTRAINT DF_Products_UpdatedAt DEFAULT SYSUTCDATETIME(),
        CONSTRAINT FK_Products_Companies FOREIGN KEY (CompanyID)
            REFERENCES dbo.Companies(CompanyID),
        CONSTRAINT FK_Products_CompanyCategory FOREIGN KEY (CompanyID, CategoryID)
            REFERENCES dbo.ProductCategories(CompanyID, CategoryID),
        CONSTRAINT FK_Products_UnitsOfMeasure FOREIGN KEY (UnitID)
            REFERENCES dbo.UnitsOfMeasure(UnitID),
        CONSTRAINT CK_Products_ProductType
            CHECK (ProductType IN (N'RAW_MATERIAL', N'FINISHED_GOOD')),
        CONSTRAINT CK_Products_ReorderLevel CHECK (ReorderLevel >= 0),
        CONSTRAINT CK_Products_SKU_NotBlank CHECK (LEN(LTRIM(RTRIM(SKU))) > 0),
        CONSTRAINT CK_Products_ProductName_NotBlank CHECK (LEN(LTRIM(RTRIM(ProductName))) > 0)
    );
END;
GO

IF COL_LENGTH(N'dbo.Products', N'QuantityOnHand') IS NULL
BEGIN
    ALTER TABLE dbo.Products ADD QuantityOnHand DECIMAL(18,3) NOT NULL
        CONSTRAINT DF_Products_QuantityOnHand DEFAULT (0) WITH VALUES;
END;
GO

IF NOT EXISTS (
    SELECT 1 FROM sys.indexes
    WHERE object_id = OBJECT_ID(N'dbo.Products') AND name = N'UQ_Products_Company_SKU'
)
    CREATE UNIQUE INDEX UQ_Products_Company_SKU ON dbo.Products(CompanyID, SKU);
GO

IF NOT EXISTS (
    SELECT 1 FROM sys.indexes
    WHERE object_id = OBJECT_ID(N'dbo.Products') AND name = N'IX_Products_Company_Name'
)
    CREATE INDEX IX_Products_Company_Name ON dbo.Products(CompanyID, ProductName);
GO

IF NOT EXISTS (
    SELECT 1 FROM sys.indexes
    WHERE object_id = OBJECT_ID(N'dbo.Products') AND name = N'IX_Products_Company_Category'
)
    CREATE INDEX IX_Products_Company_Category ON dbo.Products(CompanyID, CategoryID);
GO

/* Company-owned supplier directory. Additive and safe to rerun. The composite
   unique key supports future company-safe purchasing foreign keys. */
IF OBJECT_ID(N'dbo.Suppliers', N'U') IS NULL
BEGIN
    CREATE TABLE dbo.Suppliers
    (
        SupplierID INT IDENTITY(1,1) NOT NULL CONSTRAINT PK_Suppliers PRIMARY KEY,
        CompanyID INT NOT NULL,
        SupplierCode NVARCHAR(40) NOT NULL,
        SupplierName NVARCHAR(180) NOT NULL,
        ContactPerson NVARCHAR(160) NULL,
        Email NVARCHAR(254) NULL,
        Phone NVARCHAR(40) NULL,
        AlternatePhone NVARCHAR(40) NULL,
        Address NVARCHAR(400) NULL,
        City NVARCHAR(100) NULL,
        Country NVARCHAR(100) NULL,
        TaxRegistrationNumber NVARCHAR(50) NULL,
        PaymentTerms NVARCHAR(100) NULL,
        Notes NVARCHAR(1000) NULL,
        SupplierStatus NVARCHAR(20) NOT NULL
            CONSTRAINT DF_Suppliers_SupplierStatus DEFAULT N'ACTIVE',
        CreatedAt DATETIME2(0) NOT NULL
            CONSTRAINT DF_Suppliers_CreatedAt DEFAULT SYSUTCDATETIME(),
        UpdatedAt DATETIME2(0) NOT NULL
            CONSTRAINT DF_Suppliers_UpdatedAt DEFAULT SYSUTCDATETIME(),
        CONSTRAINT FK_Suppliers_Companies FOREIGN KEY (CompanyID)
            REFERENCES dbo.Companies(CompanyID),
        CONSTRAINT CK_Suppliers_SupplierStatus
            CHECK (SupplierStatus IN (N'ACTIVE', N'INACTIVE')),
        CONSTRAINT CK_Suppliers_SupplierCode_NotBlank
            CHECK (LEN(LTRIM(RTRIM(SupplierCode))) > 0),
        CONSTRAINT CK_Suppliers_SupplierName_NotBlank
            CHECK (LEN(LTRIM(RTRIM(SupplierName))) > 0)
    );
END;
GO

IF NOT EXISTS (
    SELECT 1 FROM sys.indexes
    WHERE object_id = OBJECT_ID(N'dbo.Suppliers') AND name = N'UQ_Suppliers_Company_Code'
)
    CREATE UNIQUE INDEX UQ_Suppliers_Company_Code
        ON dbo.Suppliers(CompanyID, SupplierCode);
GO

IF NOT EXISTS (
    SELECT 1 FROM sys.indexes
    WHERE object_id = OBJECT_ID(N'dbo.Suppliers') AND name = N'UQ_Suppliers_Company_SupplierID'
)
    CREATE UNIQUE INDEX UQ_Suppliers_Company_SupplierID
        ON dbo.Suppliers(CompanyID, SupplierID);
GO

IF NOT EXISTS (
    SELECT 1 FROM sys.indexes
    WHERE object_id = OBJECT_ID(N'dbo.Suppliers') AND name = N'IX_Suppliers_Company_Status_Name'
)
    CREATE INDEX IX_Suppliers_Company_Status_Name
        ON dbo.Suppliers(CompanyID, SupplierStatus, SupplierName);
GO

/*
   User-level permissions. Existing users retain their current role-based
   inventory access through PermissionsConfigured = 0. New company users
   receive only the explicit permissions selected by their administrator.
*/
IF COL_LENGTH(N'dbo.Users', N'PermissionsConfigured') IS NULL
BEGIN
    ALTER TABLE dbo.Users ADD PermissionsConfigured BIT NOT NULL
        CONSTRAINT DF_Users_PermissionsConfigured DEFAULT (0) WITH VALUES;
END;
GO

-- Password recovery support. Existing users retain their current access and
-- receive token version 0; no user records are recreated or reset.
IF COL_LENGTH(N'dbo.Users', N'MustChangePassword') IS NULL
BEGIN
    ALTER TABLE dbo.Users ADD MustChangePassword BIT NOT NULL
        CONSTRAINT DF_Users_MustChangePassword DEFAULT (0) WITH VALUES;
END;
GO

IF COL_LENGTH(N'dbo.Users', N'AuthVersion') IS NULL
BEGIN
    ALTER TABLE dbo.Users ADD AuthVersion INT NOT NULL
        CONSTRAINT DF_Users_AuthVersion DEFAULT (0) WITH VALUES;
END;
GO

IF COL_LENGTH(N'dbo.Users', N'TemporaryPasswordExpiresAt') IS NULL
BEGIN
    ALTER TABLE dbo.Users ADD TemporaryPasswordExpiresAt DATETIME2(0) NULL;
END;
GO

IF OBJECT_ID(N'dbo.PasswordSecurityAudit', N'U') IS NULL
BEGIN
    CREATE TABLE dbo.PasswordSecurityAudit
    (
        AuditID BIGINT IDENTITY(1,1) NOT NULL
            CONSTRAINT PK_PasswordSecurityAudit PRIMARY KEY,
        UserID INT NOT NULL,
        ActorUserID INT NULL,
        EventType NVARCHAR(60) NOT NULL,
        SourceIP NVARCHAR(45) NULL,
        CreatedAt DATETIME2(0) NOT NULL
            CONSTRAINT DF_PasswordSecurityAudit_CreatedAt DEFAULT SYSUTCDATETIME(),
        CONSTRAINT FK_PasswordSecurityAudit_User FOREIGN KEY (UserID)
            REFERENCES dbo.Users(UserID),
        CONSTRAINT FK_PasswordSecurityAudit_Actor FOREIGN KEY (ActorUserID)
            REFERENCES dbo.Users(UserID)
    );
    CREATE INDEX IX_PasswordSecurityAudit_User_CreatedAt
        ON dbo.PasswordSecurityAudit(UserID, CreatedAt DESC);
END;
GO

IF OBJECT_ID(N'dbo.PermissionCatalog', N'U') IS NULL
BEGIN
    CREATE TABLE dbo.PermissionCatalog
    (
        PermissionCode NVARCHAR(80) NOT NULL CONSTRAINT PK_PermissionCatalog PRIMARY KEY,
        PermissionName NVARCHAR(120) NOT NULL,
        CreatedAt DATETIME2(0) NOT NULL
            CONSTRAINT DF_PermissionCatalog_CreatedAt DEFAULT SYSUTCDATETIME()
    );
END;
GO

IF OBJECT_ID(N'dbo.UserPermissions', N'U') IS NULL
BEGIN
    CREATE TABLE dbo.UserPermissions
    (
        UserID INT NOT NULL,
        PermissionCode NVARCHAR(80) NOT NULL,
        GrantedByUserID INT NULL,
        GrantedAt DATETIME2(0) NOT NULL
            CONSTRAINT DF_UserPermissions_GrantedAt DEFAULT SYSUTCDATETIME(),
        CONSTRAINT PK_UserPermissions PRIMARY KEY (UserID, PermissionCode),
        CONSTRAINT FK_UserPermissions_Users FOREIGN KEY (UserID)
            REFERENCES dbo.Users(UserID),
        CONSTRAINT FK_UserPermissions_Catalog FOREIGN KEY (PermissionCode)
            REFERENCES dbo.PermissionCatalog(PermissionCode),
        CONSTRAINT FK_UserPermissions_GrantedBy FOREIGN KEY (GrantedByUserID)
            REFERENCES dbo.Users(UserID)
    );
END;
GO

INSERT INTO dbo.PermissionCatalog (PermissionCode, PermissionName)
SELECT seed.PermissionCode, seed.PermissionName
FROM (VALUES
    (N'dashboard.view', N'View dashboard'),
    (N'dashboard.company_overview', N'View company overview metrics'),
    (N'users.view', N'View company users'),
    (N'users.create', N'Create company users'),
    (N'users.update', N'Edit company users'),
    (N'users.deactivate', N'Activate or deactivate users'),
    (N'users.delete', N'Permanently delete company users'),
    (N'users.assign_role', N'Assign roles and permissions'),
    (N'inventory.view', N'View inventory'),
    (N'inventory.create', N'Create inventory records'),
    (N'inventory.update', N'Edit inventory records'),
    (N'suppliers.view', N'View company suppliers'),
    (N'suppliers.create', N'Create company suppliers'),
    (N'suppliers.update', N'Edit company suppliers'),
    (N'suppliers.deactivate', N'Activate or deactivate suppliers')
) AS seed(PermissionCode, PermissionName)
WHERE NOT EXISTS
    (SELECT 1 FROM dbo.PermissionCatalog p WHERE p.PermissionCode = seed.PermissionCode);
GO

/* 3. Finished-garment variants, selling price, barcode, and purchasing. */
IF COL_LENGTH(N'dbo.Products', N'VariantDesign') IS NULL
    ALTER TABLE dbo.Products ADD VariantDesign NVARCHAR(100) NULL;
GO
IF COL_LENGTH(N'dbo.Products', N'VariantSize') IS NULL
    ALTER TABLE dbo.Products ADD VariantSize NVARCHAR(40) NULL;
GO
IF COL_LENGTH(N'dbo.Products', N'VariantColor') IS NULL
    ALTER TABLE dbo.Products ADD VariantColor NVARCHAR(50) NULL;
GO
IF COL_LENGTH(N'dbo.Products', N'SellingPrice') IS NULL
    ALTER TABLE dbo.Products ADD SellingPrice DECIMAL(18,2) NULL;
GO
IF COL_LENGTH(N'dbo.Products', N'BarcodeValue') IS NULL
    ALTER TABLE dbo.Products ADD BarcodeValue NVARCHAR(64) NULL;
GO

IF NOT EXISTS (SELECT 1 FROM sys.check_constraints WHERE name = N'CK_Products_SellingPrice_NonNegative')
    ALTER TABLE dbo.Products ADD CONSTRAINT CK_Products_SellingPrice_NonNegative
        CHECK (SellingPrice IS NULL OR SellingPrice >= 0);
GO
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE object_id = OBJECT_ID(N'dbo.Products') AND name = N'UQ_Products_BarcodeValue')
    CREATE UNIQUE INDEX UQ_Products_BarcodeValue ON dbo.Products(BarcodeValue)
        WHERE BarcodeValue IS NOT NULL;
GO
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE object_id = OBJECT_ID(N'dbo.Products') AND name = N'UQ_Products_Company_ProductID')
    CREATE UNIQUE INDEX UQ_Products_Company_ProductID ON dbo.Products(CompanyID, ProductID);
GO

IF NOT EXISTS (SELECT 1 FROM sys.sequences WHERE object_id = OBJECT_ID(N'dbo.PurchaseOrderNumberSequence'))
    CREATE SEQUENCE dbo.PurchaseOrderNumberSequence AS BIGINT START WITH 1 INCREMENT BY 1 NO CYCLE;
GO

IF OBJECT_ID(N'dbo.PurchaseOrders', N'U') IS NULL
BEGIN
    CREATE TABLE dbo.PurchaseOrders
    (
        PurchaseOrderID INT IDENTITY(1,1) NOT NULL CONSTRAINT PK_PurchaseOrders PRIMARY KEY,
        PurchaseOrderNumber NVARCHAR(32) NOT NULL,
        CompanyID INT NOT NULL,
        SupplierID INT NOT NULL,
        OrderDate DATE NOT NULL,
        ExpectedDeliveryDate DATE NULL,
        Status NVARCHAR(24) NOT NULL CONSTRAINT DF_PurchaseOrders_Status DEFAULT N'DRAFT',
        Subtotal DECIMAL(19,2) NOT NULL,
        TotalAmount DECIMAL(19,2) NOT NULL,
        Notes NVARCHAR(1000) NULL,
        CreatedByUserID INT NOT NULL,
        CreatedAt DATETIME2(0) NOT NULL CONSTRAINT DF_PurchaseOrders_CreatedAt DEFAULT SYSUTCDATETIME(),
        UpdatedAt DATETIME2(0) NOT NULL CONSTRAINT DF_PurchaseOrders_UpdatedAt DEFAULT SYSUTCDATETIME(),
        CONSTRAINT FK_PurchaseOrders_Companies FOREIGN KEY (CompanyID) REFERENCES dbo.Companies(CompanyID),
        CONSTRAINT FK_PurchaseOrders_Suppliers FOREIGN KEY (CompanyID, SupplierID) REFERENCES dbo.Suppliers(CompanyID, SupplierID),
        CONSTRAINT FK_PurchaseOrders_CreatedBy FOREIGN KEY (CreatedByUserID) REFERENCES dbo.Users(UserID),
        CONSTRAINT CK_PurchaseOrders_Status CHECK (Status IN (N'DRAFT', N'SUBMITTED', N'PARTIALLY_RECEIVED', N'COMPLETED', N'CANCELLED')),
        CONSTRAINT CK_PurchaseOrders_Amounts CHECK (Subtotal >= 0 AND TotalAmount >= 0 AND Subtotal = TotalAmount),
        CONSTRAINT CK_PurchaseOrders_DeliveryDate CHECK (ExpectedDeliveryDate IS NULL OR ExpectedDeliveryDate >= OrderDate)
    );
END;
GO
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE object_id = OBJECT_ID(N'dbo.PurchaseOrders') AND name = N'UQ_PurchaseOrders_Number')
    CREATE UNIQUE INDEX UQ_PurchaseOrders_Number ON dbo.PurchaseOrders(PurchaseOrderNumber);
GO
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE object_id = OBJECT_ID(N'dbo.PurchaseOrders') AND name = N'UQ_PurchaseOrders_Company_OrderID')
    CREATE UNIQUE INDEX UQ_PurchaseOrders_Company_OrderID ON dbo.PurchaseOrders(CompanyID, PurchaseOrderID);
GO
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE object_id = OBJECT_ID(N'dbo.PurchaseOrders') AND name = N'IX_PurchaseOrders_Company_Date')
    CREATE INDEX IX_PurchaseOrders_Company_Date ON dbo.PurchaseOrders(CompanyID, OrderDate DESC, PurchaseOrderID DESC);
GO
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE object_id = OBJECT_ID(N'dbo.PurchaseOrders') AND name = N'IX_PurchaseOrders_Company_Supplier_Status')
    CREATE INDEX IX_PurchaseOrders_Company_Supplier_Status ON dbo.PurchaseOrders(CompanyID, SupplierID, Status);
GO

IF OBJECT_ID(N'dbo.PurchaseOrderItems', N'U') IS NULL
BEGIN
    CREATE TABLE dbo.PurchaseOrderItems
    (
        PurchaseOrderItemID INT IDENTITY(1,1) NOT NULL CONSTRAINT PK_PurchaseOrderItems PRIMARY KEY,
        CompanyID INT NOT NULL,
        PurchaseOrderID INT NOT NULL,
        ProductID INT NOT NULL,
        SKU NVARCHAR(60) NOT NULL,
        ProductName NVARCHAR(180) NOT NULL,
        VariantDesign NVARCHAR(100) NULL,
        VariantSize NVARCHAR(40) NULL,
        VariantColor NVARCHAR(50) NULL,
        UnitCode NVARCHAR(16) NOT NULL,
        Quantity DECIMAL(18,3) NOT NULL,
        UnitCost DECIMAL(18,2) NOT NULL,
        LineTotal DECIMAL(19,2) NOT NULL,
        CreatedAt DATETIME2(0) NOT NULL CONSTRAINT DF_PurchaseOrderItems_CreatedAt DEFAULT SYSUTCDATETIME(),
        CONSTRAINT FK_PurchaseOrderItems_Order FOREIGN KEY (CompanyID, PurchaseOrderID) REFERENCES dbo.PurchaseOrders(CompanyID, PurchaseOrderID),
        CONSTRAINT FK_PurchaseOrderItems_Product FOREIGN KEY (CompanyID, ProductID) REFERENCES dbo.Products(CompanyID, ProductID),
        CONSTRAINT CK_PurchaseOrderItems_Quantity CHECK (Quantity > 0),
        CONSTRAINT CK_PurchaseOrderItems_Cost CHECK (UnitCost >= 0),
        CONSTRAINT CK_PurchaseOrderItems_Total CHECK (LineTotal >= 0)
    );
END;
GO
IF COL_LENGTH(N'dbo.PurchaseOrderItems', N'VariantDesign') IS NULL
    ALTER TABLE dbo.PurchaseOrderItems ADD VariantDesign NVARCHAR(100) NULL;
GO
IF COL_LENGTH(N'dbo.PurchaseOrderItems', N'VariantSize') IS NULL
    ALTER TABLE dbo.PurchaseOrderItems ADD VariantSize NVARCHAR(40) NULL;
GO
IF COL_LENGTH(N'dbo.PurchaseOrderItems', N'VariantColor') IS NULL
    ALTER TABLE dbo.PurchaseOrderItems ADD VariantColor NVARCHAR(50) NULL;
GO
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE object_id = OBJECT_ID(N'dbo.PurchaseOrderItems') AND name = N'IX_PurchaseOrderItems_Order')
    CREATE INDEX IX_PurchaseOrderItems_Order ON dbo.PurchaseOrderItems(CompanyID, PurchaseOrderID, PurchaseOrderItemID);
GO

IF OBJECT_ID(N'dbo.PurchaseOrderStatusHistory', N'U') IS NULL
BEGIN
    CREATE TABLE dbo.PurchaseOrderStatusHistory
    (
        PurchaseOrderStatusHistoryID BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT PK_PurchaseOrderStatusHistory PRIMARY KEY,
        CompanyID INT NOT NULL,
        PurchaseOrderID INT NOT NULL,
        Status NVARCHAR(24) NOT NULL,
        ChangedByUserID INT NOT NULL,
        Note NVARCHAR(500) NULL,
        ChangedAt DATETIME2(0) NOT NULL CONSTRAINT DF_PurchaseOrderStatusHistory_ChangedAt DEFAULT SYSUTCDATETIME(),
        CONSTRAINT FK_PurchaseOrderStatusHistory_Order FOREIGN KEY (CompanyID, PurchaseOrderID) REFERENCES dbo.PurchaseOrders(CompanyID, PurchaseOrderID),
        CONSTRAINT FK_PurchaseOrderStatusHistory_User FOREIGN KEY (ChangedByUserID) REFERENCES dbo.Users(UserID)
    );
END;
GO
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE object_id = OBJECT_ID(N'dbo.PurchaseOrderStatusHistory') AND name = N'IX_PurchaseOrderStatusHistory_Order')
    CREATE INDEX IX_PurchaseOrderStatusHistory_Order ON dbo.PurchaseOrderStatusHistory(CompanyID, PurchaseOrderID, ChangedAt);
GO

INSERT INTO dbo.PermissionCatalog (PermissionCode, PermissionName)
SELECT seed.PermissionCode, seed.PermissionName
FROM (VALUES
    (N'purchasing.view', N'View purchase orders'),
    (N'purchasing.create', N'Create purchase orders'),
    (N'purchasing.update', N'Edit draft purchase orders'),
    (N'purchasing.submit', N'Submit purchase orders'),
    (N'purchasing.cancel', N'Cancel purchase orders'),
    (N'inventory.barcode.manage', N'Generate and manage finished-garment barcodes')
) AS seed(PermissionCode, PermissionName)
WHERE NOT EXISTS (SELECT 1 FROM dbo.PermissionCatalog p WHERE p.PermissionCode = seed.PermissionCode);
GO

GO

-- 4. Verify setup without displaying personal information or password hashes.
USE [GBMS_Database];
GO
SELECT N'Companies' AS TableName, COUNT_BIG(*) AS RecordCount FROM dbo.Companies
UNION ALL
SELECT N'Users', COUNT_BIG(*) FROM dbo.Users
UNION ALL
SELECT N'Roles', COUNT_BIG(*) FROM dbo.Roles
UNION ALL
SELECT N'ProductCategories', COUNT_BIG(*) FROM dbo.ProductCategories
UNION ALL
SELECT N'Products', COUNT_BIG(*) FROM dbo.Products
UNION ALL
SELECT N'Suppliers', COUNT_BIG(*) FROM dbo.Suppliers;
GO
SELECT N'PurchaseOrders', COUNT_BIG(*) FROM dbo.PurchaseOrders
UNION ALL
SELECT N'PurchaseOrderItems', COUNT_BIG(*) FROM dbo.PurchaseOrderItems;
GO
SELECT RoleName, Description FROM dbo.Roles ORDER BY RoleID;
GO
SELECT PermissionCode, PermissionName FROM dbo.PermissionCatalog ORDER BY PermissionCode;
GO


