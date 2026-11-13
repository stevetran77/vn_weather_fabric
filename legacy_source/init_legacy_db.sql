-- Creates the Legacy source: database, logins for Fabric, and the legacy-style tables.
-- Run with sqlcmd, passing both passwords as variables:
--   sqlcmd -C -S localhost -U sa -P "$SA_PASSWORD" \
--     -v READER_PASSWORD="$READER_PASSWORD" WRITER_PASSWORD="$WRITER_PASSWORD" -i init_legacy_db.sql
-- The script is safe to run more than once.
--
-- The tables deliberately look like an old system, not like the Gold tables:
--   * its own table and column names
--   * obs_time is LOCAL time (Asia/Ho_Chi_Minh, UTC+7, no daylight saving), not UTC
--   * measures are FLOAT so values copied from Gold stay identical

IF DB_ID('legacy_weather') IS NULL
    CREATE DATABASE legacy_weather;
GO

IF SUSER_ID('fabric_reader') IS NULL
    CREATE LOGIN fabric_reader WITH PASSWORD = '$(READER_PASSWORD)', CHECK_POLICY = OFF;
GO

IF SUSER_ID('fabric_loader') IS NULL
    CREATE LOGIN fabric_loader WITH PASSWORD = '$(WRITER_PASSWORD)', CHECK_POLICY = OFF;
GO

USE legacy_weather;
GO

IF USER_ID('fabric_reader') IS NULL
    CREATE USER fabric_reader FOR LOGIN fabric_reader;
GO

IF USER_ID('fabric_loader') IS NULL
    CREATE USER fabric_loader FOR LOGIN fabric_loader;
GO

ALTER ROLE db_datareader ADD MEMBER fabric_reader;
ALTER ROLE db_datareader ADD MEMBER fabric_loader;
ALTER ROLE db_datawriter ADD MEMBER fabric_loader;
GO

IF OBJECT_ID('dbo.city') IS NULL
    CREATE TABLE dbo.city (
        city_code     INT           NOT NULL PRIMARY KEY,
        city_name     NVARCHAR(100) NOT NULL,
        lat           FLOAT         NOT NULL,
        lon           FLOAT         NOT NULL,
        province_code INT           NOT NULL,
        province_name NVARCHAR(100) NOT NULL
    );
GO

IF OBJECT_ID('dbo.weather_hourly') IS NULL
    CREATE TABLE dbo.weather_hourly (
        city_code    INT       NOT NULL REFERENCES dbo.city (city_code),
        obs_time     DATETIME2(0) NOT NULL,  -- local time, UTC+7
        temp_c       FLOAT     NULL,
        humidity_pct FLOAT     NULL,
        rain_mm      FLOAT     NULL,
        wind_kmh     FLOAT     NULL,
        pm25         FLOAT     NULL,
        CONSTRAINT pk_weather_hourly PRIMARY KEY (city_code, obs_time)
    );
GO
