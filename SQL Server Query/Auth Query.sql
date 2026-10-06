IF DB_ID(N'GBMS') IS NULL
    CREATE DATABASE [GBMS];
GO

USE [GBMS];
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
    VALUES (N'SUPER_ADMIN', N'Full access to the GBMS workspace');
GO

Select * from Users;