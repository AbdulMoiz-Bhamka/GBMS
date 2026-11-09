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

/* 3a. Finished-garment barcode audit and company-scoped material plan.
   Additive and safe to rerun; existing barcode values and product data are kept. */
IF COL_LENGTH(N'dbo.Products', N'BarcodeGeneratedAt') IS NULL
    ALTER TABLE dbo.Products ADD BarcodeGeneratedAt DATETIME2(0) NULL;
GO
IF COL_LENGTH(N'dbo.Products', N'BarcodeGeneratedByUserID') IS NULL
    ALTER TABLE dbo.Products ADD BarcodeGeneratedByUserID INT NULL;
GO
IF NOT EXISTS (
    SELECT 1 FROM sys.foreign_keys
    WHERE name = N'FK_Products_BarcodeGeneratedByUser'
      AND parent_object_id = OBJECT_ID(N'dbo.Products')
)
    ALTER TABLE dbo.Products ADD CONSTRAINT FK_Products_BarcodeGeneratedByUser
        FOREIGN KEY (BarcodeGeneratedByUserID) REFERENCES dbo.Users(UserID);
GO

IF OBJECT_ID(N'dbo.FinishedGoodMaterialComponents', N'U') IS NULL
BEGIN
    CREATE TABLE dbo.FinishedGoodMaterialComponents
    (
        CompanyID INT NOT NULL,
        FinishedGoodProductID INT NOT NULL,
        RawMaterialProductID INT NOT NULL,
        QuantityPerFinishedUnit DECIMAL(18,6) NOT NULL,
        CreatedAt DATETIME2(0) NOT NULL
            CONSTRAINT DF_FGMC_CreatedAt DEFAULT SYSUTCDATETIME(),
        CreatedByUserID INT NOT NULL,
        CONSTRAINT PK_FinishedGoodMaterialComponents PRIMARY KEY
            (CompanyID, FinishedGoodProductID, RawMaterialProductID),
        CONSTRAINT FK_FGMC_FinishedProduct FOREIGN KEY (CompanyID, FinishedGoodProductID)
            REFERENCES dbo.Products(CompanyID, ProductID),
        CONSTRAINT FK_FGMC_RawMaterial FOREIGN KEY (CompanyID, RawMaterialProductID)
            REFERENCES dbo.Products(CompanyID, ProductID),
        CONSTRAINT FK_FGMC_CreatedBy FOREIGN KEY (CreatedByUserID)
            REFERENCES dbo.Users(UserID),
        CONSTRAINT CK_FGMC_Quantity CHECK (QuantityPerFinishedUnit > 0)
    );
END;
GO
IF NOT EXISTS (
    SELECT 1 FROM sys.indexes
    WHERE object_id = OBJECT_ID(N'dbo.FinishedGoodMaterialComponents')
      AND name = N'IX_FGMC_Company_RawMaterial'
)
    CREATE INDEX IX_FGMC_Company_RawMaterial
        ON dbo.FinishedGoodMaterialComponents(CompanyID, RawMaterialProductID);
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
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE object_id = OBJECT_ID(N'dbo.PurchaseOrderItems') AND name = N'UQ_PurchaseOrderItems_Company_ItemID')
    CREATE UNIQUE INDEX UQ_PurchaseOrderItems_Company_ItemID ON dbo.PurchaseOrderItems(CompanyID,PurchaseOrderItemID);
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

-- Inventory stock ledger. This is additive and safe to rerun; existing product
-- balances are preserved and recorded once as opening-stock transactions.
IF OBJECT_ID(N'dbo.InventoryTransactions', N'U') IS NULL
BEGIN
    CREATE TABLE dbo.InventoryTransactions
    (
        InventoryTransactionID BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT PK_InventoryTransactions PRIMARY KEY,
        CompanyID INT NOT NULL,
        ProductID INT NOT NULL,
        TransactionType NVARCHAR(32) NOT NULL,
        QuantityChanged DECIMAL(18,3) NOT NULL,
        PreviousBalance DECIMAL(18,3) NOT NULL,
        NewBalance DECIMAL(18,3) NOT NULL,
        SupplierID INT NULL,
        PurchaseOrderID INT NULL,
        ReferenceNumber NVARCHAR(120) NULL,
        CreatedByUserID INT NULL,
        TransactionAt DATETIME2(0) NOT NULL CONSTRAINT DF_InventoryTransactions_TransactionAt DEFAULT SYSUTCDATETIME(),
        Notes NVARCHAR(1000) NULL,
        IdempotencyKey UNIQUEIDENTIFIER NOT NULL,
        CONSTRAINT FK_InventoryTransactions_Product FOREIGN KEY (CompanyID, ProductID) REFERENCES dbo.Products(CompanyID, ProductID),
        CONSTRAINT FK_InventoryTransactions_Supplier FOREIGN KEY (CompanyID, SupplierID) REFERENCES dbo.Suppliers(CompanyID, SupplierID),
        CONSTRAINT FK_InventoryTransactions_Order FOREIGN KEY (CompanyID, PurchaseOrderID) REFERENCES dbo.PurchaseOrders(CompanyID, PurchaseOrderID),
        CONSTRAINT FK_InventoryTransactions_User FOREIGN KEY (CreatedByUserID) REFERENCES dbo.Users(UserID) ON DELETE SET NULL,
        CONSTRAINT CK_InventoryTransactions_Type CHECK (TransactionType IN
            (N'OPENING_STOCK',N'STOCK_RECEIPT',N'STOCK_ISSUE',N'PRODUCTION_CONSUMPTION',N'PRODUCTION_OUTPUT',N'STOCK_ADJUSTMENT')),
        CONSTRAINT CK_InventoryTransactions_Quantity CHECK (QuantityChanged <> 0),
        CONSTRAINT CK_InventoryTransactions_Balance CHECK (PreviousBalance >= 0 AND NewBalance >= 0 AND NewBalance = PreviousBalance + QuantityChanged)
    );
END;
GO
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE object_id = OBJECT_ID(N'dbo.InventoryTransactions') AND name = N'UQ_InventoryTransactions_Company_Idempotency')
    CREATE UNIQUE INDEX UQ_InventoryTransactions_Company_Idempotency ON dbo.InventoryTransactions(CompanyID, IdempotencyKey);
GO
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE object_id = OBJECT_ID(N'dbo.InventoryTransactions') AND name = N'IX_InventoryTransactions_Company_Product_Date')
    CREATE INDEX IX_InventoryTransactions_Company_Product_Date ON dbo.InventoryTransactions(CompanyID, ProductID, TransactionAt DESC, InventoryTransactionID DESC);
GO
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE object_id = OBJECT_ID(N'dbo.InventoryTransactions') AND name = N'UX_InventoryTransactions_Opening')
    CREATE UNIQUE INDEX UX_InventoryTransactions_Opening ON dbo.InventoryTransactions(CompanyID, ProductID) WHERE TransactionType = N'OPENING_STOCK';
GO
INSERT INTO dbo.InventoryTransactions
    (CompanyID, ProductID, TransactionType, QuantityChanged, PreviousBalance,
     NewBalance, CreatedByUserID, TransactionAt, Notes, IdempotencyKey)
SELECT p.CompanyID, p.ProductID, N'OPENING_STOCK', p.QuantityOnHand, 0,
       p.QuantityOnHand, NULL, p.CreatedAt, N'Opening balance captured during stock-ledger setup.', NEWID()
FROM dbo.Products p
WHERE p.QuantityOnHand > 0
  AND NOT EXISTS (SELECT 1 FROM dbo.InventoryTransactions t
                  WHERE t.CompanyID = p.CompanyID AND t.ProductID = p.ProductID
                    AND t.TransactionType = N'OPENING_STOCK');
GO

/* Manufacturing foundation. Additive only: existing products, stock, purchase
   orders and transaction history are retained. */
IF COL_LENGTH(N'dbo.InventoryTransactions', N'MaterialLotID') IS NULL
    ALTER TABLE dbo.InventoryTransactions ADD MaterialLotID BIGINT NULL;
GO
IF COL_LENGTH(N'dbo.InventoryTransactions', N'GoodsReceiptID') IS NULL
    ALTER TABLE dbo.InventoryTransactions ADD GoodsReceiptID BIGINT NULL;
GO
IF COL_LENGTH(N'dbo.InventoryTransactions', N'ProductionBatchID') IS NULL
    ALTER TABLE dbo.InventoryTransactions ADD ProductionBatchID BIGINT NULL;
GO
IF OBJECT_ID(N'dbo.GoodsReceipts', N'U') IS NULL
BEGIN
    CREATE TABLE dbo.GoodsReceipts
    (
        GoodsReceiptID BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT PK_GoodsReceipts PRIMARY KEY,
        CompanyID INT NOT NULL,
        ReceiptNumber NVARCHAR(40) NOT NULL,
        SupplierID INT NOT NULL,
        PurchaseOrderID INT NOT NULL,
        ReceivedAt DATETIME2(0) NOT NULL CONSTRAINT DF_GoodsReceipts_ReceivedAt DEFAULT SYSUTCDATETIME(),
        CreatedByUserID INT NOT NULL,
        Notes NVARCHAR(1000) NULL,
        IdempotencyKey UNIQUEIDENTIFIER NOT NULL,
        CreatedAt DATETIME2(0) NOT NULL CONSTRAINT DF_GoodsReceipts_CreatedAt DEFAULT SYSUTCDATETIME(),
        CONSTRAINT FK_GoodsReceipts_Supplier FOREIGN KEY (CompanyID,SupplierID) REFERENCES dbo.Suppliers(CompanyID,SupplierID),
        CONSTRAINT FK_GoodsReceipts_Order FOREIGN KEY (CompanyID,PurchaseOrderID) REFERENCES dbo.PurchaseOrders(CompanyID,PurchaseOrderID),
        CONSTRAINT FK_GoodsReceipts_User FOREIGN KEY (CreatedByUserID) REFERENCES dbo.Users(UserID),
        CONSTRAINT UQ_GoodsReceipts_Company_Receipt UNIQUE (CompanyID,ReceiptNumber),
        CONSTRAINT UQ_GoodsReceipts_Company_ID UNIQUE (CompanyID,GoodsReceiptID),
        CONSTRAINT UQ_GoodsReceipts_Idempotency UNIQUE (CompanyID,IdempotencyKey)
    );
END;
GO
IF OBJECT_ID(N'dbo.MaterialLots', N'U') IS NULL
BEGIN
    CREATE TABLE dbo.MaterialLots
    (
        MaterialLotID BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT PK_MaterialLots PRIMARY KEY,
        CompanyID INT NOT NULL,
        ProductID INT NOT NULL,
        GoodsReceiptID BIGINT NOT NULL,
        LotNumber NVARCHAR(60) NOT NULL,
        OriginalQuantity DECIMAL(18,3) NOT NULL,
        RemainingQuantity DECIMAL(18,3) NOT NULL,
        CreatedAt DATETIME2(0) NOT NULL CONSTRAINT DF_MaterialLots_CreatedAt DEFAULT SYSUTCDATETIME(),
        CONSTRAINT FK_MaterialLots_Product FOREIGN KEY (CompanyID,ProductID) REFERENCES dbo.Products(CompanyID,ProductID),
        CONSTRAINT FK_MaterialLots_Receipt FOREIGN KEY (CompanyID,GoodsReceiptID) REFERENCES dbo.GoodsReceipts(CompanyID,GoodsReceiptID),
        CONSTRAINT CK_MaterialLots_Quantity CHECK (OriginalQuantity > 0 AND RemainingQuantity >= 0 AND RemainingQuantity <= OriginalQuantity),
        CONSTRAINT UQ_MaterialLots_Company_ID UNIQUE (CompanyID,MaterialLotID),
        CONSTRAINT UQ_MaterialLots_Company_Number UNIQUE (CompanyID,LotNumber)
    );
END;
GO
IF OBJECT_ID(N'dbo.GoodsReceiptItems', N'U') IS NULL
BEGIN
    CREATE TABLE dbo.GoodsReceiptItems
    (
        GoodsReceiptItemID BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT PK_GoodsReceiptItems PRIMARY KEY,
        CompanyID INT NOT NULL,
        GoodsReceiptID BIGINT NOT NULL,
        PurchaseOrderID INT NOT NULL,
        ProductID INT NOT NULL,
        PurchaseOrderItemID INT NULL,
        MaterialLotID BIGINT NOT NULL,
        ReceivedQuantity DECIMAL(18,3) NOT NULL,
        UnitCost DECIMAL(18,2) NULL,
        CONSTRAINT FK_GoodsReceiptItems_Receipt FOREIGN KEY (CompanyID,GoodsReceiptID) REFERENCES dbo.GoodsReceipts(CompanyID,GoodsReceiptID),
        CONSTRAINT FK_GoodsReceiptItems_Order FOREIGN KEY (CompanyID,PurchaseOrderID) REFERENCES dbo.PurchaseOrders(CompanyID,PurchaseOrderID),
        CONSTRAINT FK_GoodsReceiptItems_OrderItem FOREIGN KEY (CompanyID,PurchaseOrderItemID) REFERENCES dbo.PurchaseOrderItems(CompanyID,PurchaseOrderItemID),
        CONSTRAINT FK_GoodsReceiptItems_Product FOREIGN KEY (CompanyID,ProductID) REFERENCES dbo.Products(CompanyID,ProductID),
        CONSTRAINT FK_GoodsReceiptItems_Lot FOREIGN KEY (CompanyID,MaterialLotID) REFERENCES dbo.MaterialLots(CompanyID,MaterialLotID),
        CONSTRAINT CK_GoodsReceiptItems_Quantity CHECK (ReceivedQuantity > 0),
        CONSTRAINT UQ_GoodsReceiptItems_Company_ID UNIQUE (CompanyID,GoodsReceiptItemID)
    );
END;
GO
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE object_id=OBJECT_ID(N'dbo.MaterialLots') AND name=N'IX_MaterialLots_Product')
    CREATE INDEX IX_MaterialLots_Product ON dbo.MaterialLots(CompanyID,ProductID,CreatedAt DESC);
GO
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE object_id=OBJECT_ID(N'dbo.GoodsReceiptItems') AND name=N'IX_GoodsReceiptItems_Receipt')
    CREATE INDEX IX_GoodsReceiptItems_Receipt ON dbo.GoodsReceiptItems(CompanyID,GoodsReceiptID,GoodsReceiptItemID);
GO

IF OBJECT_ID(N'dbo.ProductionWorkOrders', N'U') IS NULL
BEGIN
    CREATE TABLE dbo.ProductionWorkOrders
    (
        WorkOrderID BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT PK_ProductionWorkOrders PRIMARY KEY,
        CompanyID INT NOT NULL,
        ProductID INT NOT NULL,
        WorkOrderNumber NVARCHAR(40) NOT NULL,
        PlannedQuantity DECIMAL(18,3) NOT NULL,
        Status NVARCHAR(24) NOT NULL CONSTRAINT DF_ProductionWorkOrders_Status DEFAULT N'PLANNED',
        PlannedStartDate DATE NULL,
        PlannedEndDate DATE NULL,
        CreatedByUserID INT NOT NULL,
        CreatedAt DATETIME2(0) NOT NULL CONSTRAINT DF_ProductionWorkOrders_CreatedAt DEFAULT SYSUTCDATETIME(),
        CONSTRAINT FK_ProductionWorkOrders_Product FOREIGN KEY (CompanyID,ProductID) REFERENCES dbo.Products(CompanyID,ProductID),
        CONSTRAINT FK_ProductionWorkOrders_User FOREIGN KEY (CreatedByUserID) REFERENCES dbo.Users(UserID),
        CONSTRAINT CK_ProductionWorkOrders_Quantity CHECK (PlannedQuantity > 0),
        CONSTRAINT CK_ProductionWorkOrders_Status CHECK (Status IN (N'PLANNED',N'IN_PROGRESS',N'COMPLETED',N'CANCELLED')),
        CONSTRAINT UQ_ProductionWorkOrders_Company_ID UNIQUE (CompanyID,WorkOrderID),
        CONSTRAINT UQ_ProductionWorkOrders_Company_Number UNIQUE (CompanyID,WorkOrderNumber)
    );
END;
GO
IF OBJECT_ID(N'dbo.ProductionBatches', N'U') IS NULL
BEGIN
    CREATE TABLE dbo.ProductionBatches
    (
        ProductionBatchID BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT PK_ProductionBatches PRIMARY KEY,
        CompanyID INT NOT NULL,
        WorkOrderID BIGINT NOT NULL,
        BatchNumber NVARCHAR(40) NOT NULL,
        Status NVARCHAR(24) NOT NULL CONSTRAINT DF_ProductionBatches_Status DEFAULT N'MATERIAL_ISSUED',
        StartedAt DATETIME2(0) NOT NULL CONSTRAINT DF_ProductionBatches_StartedAt DEFAULT SYSUTCDATETIME(),
        CompletedAt DATETIME2(0) NULL,
        CreatedByUserID INT NOT NULL,
        CONSTRAINT FK_ProductionBatches_WorkOrder FOREIGN KEY (CompanyID,WorkOrderID) REFERENCES dbo.ProductionWorkOrders(CompanyID,WorkOrderID),
        CONSTRAINT FK_ProductionBatches_User FOREIGN KEY (CreatedByUserID) REFERENCES dbo.Users(UserID),
        CONSTRAINT CK_ProductionBatches_Status CHECK (Status IN (N'MATERIAL_ISSUED',N'CUTTING',N'STITCHING',N'FINISHING',N'QUALITY',N'PACKING',N'COMPLETED',N'CANCELLED')),
        CONSTRAINT UQ_ProductionBatches_Company_ID UNIQUE (CompanyID,ProductionBatchID),
        CONSTRAINT UQ_ProductionBatches_Company_Number UNIQUE (CompanyID,BatchNumber)
    );
END;
GO
IF OBJECT_ID(N'dbo.ProductionMaterialConsumptions', N'U') IS NULL
BEGIN
    CREATE TABLE dbo.ProductionMaterialConsumptions
    (
        ConsumptionID BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT PK_ProductionMaterialConsumptions PRIMARY KEY,
        CompanyID INT NOT NULL,
        ProductionBatchID BIGINT NOT NULL,
        MaterialLotID BIGINT NOT NULL,
        ProductID INT NOT NULL,
        QuantityConsumed DECIMAL(18,3) NOT NULL,
        ConsumedByUserID INT NOT NULL,
        ConsumedAt DATETIME2(0) NOT NULL CONSTRAINT DF_ProductionMaterialConsumptions_ConsumedAt DEFAULT SYSUTCDATETIME(),
        IdempotencyKey UNIQUEIDENTIFIER NOT NULL,
        Notes NVARCHAR(500) NULL,
        CONSTRAINT FK_ProductionMaterialConsumptions_Batch FOREIGN KEY (CompanyID,ProductionBatchID) REFERENCES dbo.ProductionBatches(CompanyID,ProductionBatchID),
        CONSTRAINT FK_ProductionMaterialConsumptions_Lot FOREIGN KEY (CompanyID,MaterialLotID) REFERENCES dbo.MaterialLots(CompanyID,MaterialLotID),
        CONSTRAINT FK_ProductionMaterialConsumptions_Product FOREIGN KEY (CompanyID,ProductID) REFERENCES dbo.Products(CompanyID,ProductID),
        CONSTRAINT FK_ProductionMaterialConsumptions_User FOREIGN KEY (ConsumedByUserID) REFERENCES dbo.Users(UserID),
        CONSTRAINT CK_ProductionMaterialConsumptions_Quantity CHECK (QuantityConsumed > 0),
        CONSTRAINT UQ_ProductionMaterialConsumptions_Idempotency UNIQUE (CompanyID,IdempotencyKey)
    );
END;
GO
IF OBJECT_ID(N'dbo.ProductionStageHistory', N'U') IS NULL
BEGIN
    CREATE TABLE dbo.ProductionStageHistory
    (
        StageHistoryID BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT PK_ProductionStageHistory PRIMARY KEY,
        CompanyID INT NOT NULL,
        ProductionBatchID BIGINT NOT NULL,
        Stage NVARCHAR(24) NOT NULL,
        Action NVARCHAR(24) NOT NULL,
        Quantity DECIMAL(18,3) NULL,
        WasteQuantity DECIMAL(18,3) NOT NULL CONSTRAINT DF_ProductionStageHistory_Waste DEFAULT (0),
        PerformedByUserID INT NOT NULL,
        PerformedAt DATETIME2(0) NOT NULL CONSTRAINT DF_ProductionStageHistory_PerformedAt DEFAULT SYSUTCDATETIME(),
        Notes NVARCHAR(1000) NULL,
        CONSTRAINT FK_ProductionStageHistory_Batch FOREIGN KEY (CompanyID,ProductionBatchID) REFERENCES dbo.ProductionBatches(CompanyID,ProductionBatchID),
        CONSTRAINT FK_ProductionStageHistory_User FOREIGN KEY (PerformedByUserID) REFERENCES dbo.Users(UserID),
        CONSTRAINT CK_ProductionStageHistory_Stage CHECK (Stage IN (N'CUTTING',N'STITCHING',N'FINISHING',N'QUALITY',N'PACKING')),
        CONSTRAINT CK_ProductionStageHistory_Action CHECK (Action IN (N'STARTED',N'COMPLETED',N'RECEIVED',N'REJECTED',N'REWORKED')),
        CONSTRAINT CK_ProductionStageHistory_Quantities CHECK ((Quantity IS NULL OR Quantity >= 0) AND WasteQuantity >= 0)
    );
END;
GO

IF OBJECT_ID(N'dbo.ProductionBundles', N'U') IS NULL
BEGIN
    CREATE TABLE dbo.ProductionBundles
    (
        BundleID BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT PK_ProductionBundles PRIMARY KEY,
        CompanyID INT NOT NULL,
        ProductionBatchID BIGINT NOT NULL,
        ParentBundleID BIGINT NULL,
        BundleNumber NVARCHAR(50) NOT NULL,
        Quantity DECIMAL(18,3) NOT NULL,
        Status NVARCHAR(24) NOT NULL CONSTRAINT DF_ProductionBundles_Status DEFAULT N'CUT',
        CreatedByUserID INT NOT NULL,
        CreatedAt DATETIME2(0) NOT NULL CONSTRAINT DF_ProductionBundles_CreatedAt DEFAULT SYSUTCDATETIME(),
        CONSTRAINT FK_ProductionBundles_Batch FOREIGN KEY (CompanyID,ProductionBatchID) REFERENCES dbo.ProductionBatches(CompanyID,ProductionBatchID),
        CONSTRAINT FK_ProductionBundles_Parent FOREIGN KEY (CompanyID,ParentBundleID) REFERENCES dbo.ProductionBundles(CompanyID,BundleID),
        CONSTRAINT FK_ProductionBundles_User FOREIGN KEY (CreatedByUserID) REFERENCES dbo.Users(UserID),
        CONSTRAINT CK_ProductionBundles_Quantity CHECK (Quantity > 0),
        CONSTRAINT UQ_ProductionBundles_Company_ID UNIQUE (CompanyID,BundleID),
        CONSTRAINT UQ_ProductionBundles_Company_Number UNIQUE (CompanyID,BundleNumber)
    );
END;
GO

IF OBJECT_ID(N'dbo.QualityInspections', N'U') IS NULL
BEGIN
    CREATE TABLE dbo.QualityInspections
    (
        QualityInspectionID BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT PK_QualityInspections PRIMARY KEY,
        CompanyID INT NOT NULL,
        ProductionBatchID BIGINT NOT NULL,
        InspectionStatus NVARCHAR(16) NOT NULL,
        AcceptedQuantity DECIMAL(18,3) NOT NULL,
        RejectedQuantity DECIMAL(18,3) NOT NULL,
        DefectType NVARCHAR(100) NULL,
        Notes NVARCHAR(1000) NULL,
        InspectorUserID INT NOT NULL,
        InspectedAt DATETIME2(0) NOT NULL CONSTRAINT DF_QualityInspections_InspectedAt DEFAULT SYSUTCDATETIME(),
        CONSTRAINT FK_QualityInspections_Batch FOREIGN KEY (CompanyID,ProductionBatchID) REFERENCES dbo.ProductionBatches(CompanyID,ProductionBatchID),
        CONSTRAINT FK_QualityInspections_User FOREIGN KEY (InspectorUserID) REFERENCES dbo.Users(UserID),
        CONSTRAINT CK_QualityInspections_Status CHECK (InspectionStatus IN (N'PASSED',N'PARTIAL',N'FAILED')),
        CONSTRAINT CK_QualityInspections_Quantities CHECK (AcceptedQuantity >= 0 AND RejectedQuantity >= 0 AND AcceptedQuantity + RejectedQuantity > 0)
    );
END;
GO

IF OBJECT_ID(N'dbo.FinishedGoodsRegistrations', N'U') IS NULL
BEGIN
    CREATE TABLE dbo.FinishedGoodsRegistrations
    (
        FinishedGoodsRegistrationID BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT PK_FinishedGoodsRegistrations PRIMARY KEY,
        CompanyID INT NOT NULL,
        ProductionBatchID BIGINT NOT NULL,
        ProductID INT NOT NULL,
        QuantityRegistered DECIMAL(18,3) NOT NULL,
        RegisteredByUserID INT NOT NULL,
        RegisteredAt DATETIME2(0) NOT NULL CONSTRAINT DF_FinishedGoodsRegistrations_RegisteredAt DEFAULT SYSUTCDATETIME(),
        IdempotencyKey UNIQUEIDENTIFIER NOT NULL,
        CONSTRAINT FK_FinishedGoodsRegistrations_Batch FOREIGN KEY (CompanyID,ProductionBatchID) REFERENCES dbo.ProductionBatches(CompanyID,ProductionBatchID),
        CONSTRAINT FK_FinishedGoodsRegistrations_Product FOREIGN KEY (CompanyID,ProductID) REFERENCES dbo.Products(CompanyID,ProductID),
        CONSTRAINT FK_FinishedGoodsRegistrations_User FOREIGN KEY (RegisteredByUserID) REFERENCES dbo.Users(UserID),
        CONSTRAINT CK_FinishedGoodsRegistrations_Quantity CHECK (QuantityRegistered > 0),
        CONSTRAINT UQ_FinishedGoodsRegistrations_Batch UNIQUE (CompanyID,ProductionBatchID),
        CONSTRAINT UQ_FinishedGoodsRegistrations_Idempotency UNIQUE (CompanyID,IdempotencyKey)
    );
END;
GO

IF OBJECT_ID(N'dbo.BarcodeRegistry', N'U') IS NULL
BEGIN
    CREATE TABLE dbo.BarcodeRegistry
    (
        BarcodeRegistryID BIGINT IDENTITY(1,1) NOT NULL CONSTRAINT PK_BarcodeRegistry PRIMARY KEY,
        CompanyID INT NOT NULL,
        BarcodeValue NVARCHAR(64) NOT NULL,
        EntityType NVARCHAR(24) NOT NULL,
        ProductID INT NULL,
        MaterialLotID BIGINT NULL,
        ProductionBatchID BIGINT NULL,
        BundleID BIGINT NULL,
        CreatedByUserID INT NULL,
        CreatedAt DATETIME2(0) NOT NULL CONSTRAINT DF_BarcodeRegistry_CreatedAt DEFAULT SYSUTCDATETIME(),
        CONSTRAINT FK_BarcodeRegistry_Product FOREIGN KEY (CompanyID,ProductID) REFERENCES dbo.Products(CompanyID,ProductID),
        CONSTRAINT FK_BarcodeRegistry_Lot FOREIGN KEY (CompanyID,MaterialLotID) REFERENCES dbo.MaterialLots(CompanyID,MaterialLotID),
        CONSTRAINT FK_BarcodeRegistry_Batch FOREIGN KEY (CompanyID,ProductionBatchID) REFERENCES dbo.ProductionBatches(CompanyID,ProductionBatchID),
        CONSTRAINT FK_BarcodeRegistry_Bundle FOREIGN KEY (CompanyID,BundleID) REFERENCES dbo.ProductionBundles(CompanyID,BundleID),
        CONSTRAINT FK_BarcodeRegistry_User FOREIGN KEY (CreatedByUserID) REFERENCES dbo.Users(UserID),
        CONSTRAINT CK_BarcodeRegistry_Entity CHECK
          ((EntityType=N'PRODUCT_VARIANT' AND ProductID IS NOT NULL AND MaterialLotID IS NULL AND ProductionBatchID IS NULL AND BundleID IS NULL) OR
           (EntityType=N'MATERIAL_LOT' AND ProductID IS NULL AND MaterialLotID IS NOT NULL AND ProductionBatchID IS NULL AND BundleID IS NULL) OR
           (EntityType=N'PRODUCTION_BATCH' AND ProductID IS NULL AND MaterialLotID IS NULL AND ProductionBatchID IS NOT NULL AND BundleID IS NULL) OR
           (EntityType=N'WIP_BUNDLE' AND ProductID IS NULL AND MaterialLotID IS NULL AND ProductionBatchID IS NULL AND BundleID IS NOT NULL)),
        CONSTRAINT UQ_BarcodeRegistry_Company_Value UNIQUE (CompanyID,BarcodeValue)
    );
END;
GO
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE object_id=OBJECT_ID(N'dbo.ProductionMaterialConsumptions') AND name=N'IX_ProductionMaterialConsumptions_Batch')
    CREATE INDEX IX_ProductionMaterialConsumptions_Batch ON dbo.ProductionMaterialConsumptions(CompanyID,ProductionBatchID,ConsumedAt);
GO
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE object_id=OBJECT_ID(N'dbo.BarcodeRegistry') AND name=N'IX_BarcodeRegistry_Lot')
    CREATE INDEX IX_BarcodeRegistry_Lot ON dbo.BarcodeRegistry(CompanyID,MaterialLotID) WHERE MaterialLotID IS NOT NULL;
GO

IF EXISTS (SELECT 1 FROM sys.check_constraints WHERE parent_object_id=OBJECT_ID(N'dbo.InventoryTransactions') AND name=N'CK_InventoryTransactions_Type')
    ALTER TABLE dbo.InventoryTransactions DROP CONSTRAINT CK_InventoryTransactions_Type;
GO
ALTER TABLE dbo.InventoryTransactions ADD CONSTRAINT CK_InventoryTransactions_Type CHECK (TransactionType IN
 (N'OPENING_STOCK',N'STOCK_RECEIPT',N'STOCK_ISSUE',N'GOODS_RECEIPT',N'MATERIAL_ISSUE',N'MATERIAL_CONSUMPTION',N'PRODUCTION_CONSUMPTION',N'PRODUCTION_OUTPUT',N'STOCK_TRANSFER',N'STOCK_ADJUSTMENT',N'SALES_ISSUE',N'RETURN'));
GO
IF NOT EXISTS (SELECT 1 FROM sys.foreign_keys WHERE name=N'FK_InventoryTransactions_MaterialLot')
    ALTER TABLE dbo.InventoryTransactions ADD CONSTRAINT FK_InventoryTransactions_MaterialLot FOREIGN KEY (CompanyID,MaterialLotID) REFERENCES dbo.MaterialLots(CompanyID,MaterialLotID);
GO
IF NOT EXISTS (SELECT 1 FROM sys.foreign_keys WHERE name=N'FK_InventoryTransactions_GoodsReceipt')
    ALTER TABLE dbo.InventoryTransactions ADD CONSTRAINT FK_InventoryTransactions_GoodsReceipt FOREIGN KEY (CompanyID,GoodsReceiptID) REFERENCES dbo.GoodsReceipts(CompanyID,GoodsReceiptID);
GO
IF NOT EXISTS (SELECT 1 FROM sys.foreign_keys WHERE name=N'FK_InventoryTransactions_ProductionBatch')
    ALTER TABLE dbo.InventoryTransactions ADD CONSTRAINT FK_InventoryTransactions_ProductionBatch FOREIGN KEY (CompanyID,ProductionBatchID) REFERENCES dbo.ProductionBatches(CompanyID,ProductionBatchID);
GO
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE object_id=OBJECT_ID(N'dbo.GoodsReceipts') AND name=N'IX_GoodsReceipts_Company_PO')
    CREATE INDEX IX_GoodsReceipts_Company_PO ON dbo.GoodsReceipts(CompanyID,PurchaseOrderID,ReceivedAt DESC);
GO

INSERT INTO dbo.PermissionCatalog (PermissionCode, PermissionName)
SELECT seed.PermissionCode, seed.PermissionName
FROM (VALUES
    (N'purchasing.view', N'View purchase orders'),
    (N'purchasing.create', N'Create purchase orders'),
    (N'purchasing.update', N'Edit draft purchase orders'),
    (N'purchasing.submit', N'Submit purchase orders'),
    (N'purchasing.cancel', N'Cancel purchase orders'),
    (N'inventory.barcode.manage', N'Generate and manage finished-garment barcodes'),
    (N'inventory.stock.receive', N'Receive inventory stock'),
    (N'inventory.stock.issue', N'Issue inventory stock'),
    (N'inventory.stock.adjust', N'Adjust inventory stock')
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


