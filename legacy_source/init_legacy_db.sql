-- Creates the Legacy source database and a read-only login for Fabric.
-- Run with sqlcmd, passing the reader password as a variable:
--   sqlcmd -C -S localhost -U sa -P "$SA_PASSWORD" -v READER_PASSWORD="$READER_PASSWORD" -i init_legacy_db.sql
-- The script is safe to run more than once.

IF DB_ID('legacy_weather') IS NULL
    CREATE DATABASE legacy_weather;
GO

IF SUSER_ID('fabric_reader') IS NULL
    CREATE LOGIN fabric_reader WITH PASSWORD = '$(READER_PASSWORD)', CHECK_POLICY = OFF;
GO

USE legacy_weather;
GO

IF USER_ID('fabric_reader') IS NULL
    CREATE USER fabric_reader FOR LOGIN fabric_reader;
GO

ALTER ROLE db_datareader ADD MEMBER fabric_reader;
GO

IF OBJECT_ID('dbo.connectivity_test') IS NULL
BEGIN
    CREATE TABLE dbo.connectivity_test (id INT PRIMARY KEY, note NVARCHAR(50));
    INSERT INTO dbo.connectivity_test VALUES (1, 'hello'), (2, 'from'), (3, 'legacy');
END
GO
