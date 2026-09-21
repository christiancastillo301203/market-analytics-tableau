USE MarketAnalytics;
GO


/* =========================================================
   DIMENSION: EXCHANGE
   Grain: One row per exchange
   ========================================================= */

CREATE TABLE dbo.DimExchange
(
    ExchangeID INT IDENTITY(1,1) NOT NULL,
    ExchangeCode VARCHAR(20) NOT NULL,
    ExchangeName VARCHAR(100) NOT NULL,
    MIC CHAR(4) NOT NULL,
    Country VARCHAR(100) NULL,
    Currency CHAR(3) NULL,
    TimeZone VARCHAR(50) NULL,

    CONSTRAINT PK_DimExchange
        PRIMARY KEY (ExchangeID),

    CONSTRAINT UQ_DimExchange_MIC
        UNIQUE (MIC)
);
GO


/* =========================================================
   DIMENSION: SECURITY
   Grain: One row per listed security
   ========================================================= */

CREATE TABLE dbo.DimSecurity
(
    SecurityID INT IDENTITY(1,1) NOT NULL,
    ExchangeID INT NOT NULL,
    Symbol VARCHAR(20) NOT NULL,
    CompanyName VARCHAR(200) NOT NULL,
    AssetType VARCHAR(50) NULL,
    Sector VARCHAR(100) NULL,
    Industry VARCHAR(150) NULL,
    TradingCurrency CHAR(3) NULL,

    CONSTRAINT PK_DimSecurity
        PRIMARY KEY (SecurityID),

    CONSTRAINT FK_DimSecurity_DimExchange
        FOREIGN KEY (ExchangeID)
        REFERENCES dbo.DimExchange(ExchangeID),

    CONSTRAINT UQ_DimSecurity_Exchange_Symbol
        UNIQUE (ExchangeID, Symbol)
);
GO


/* =========================================================
   FACT TABLE: DAILY PRICES
   Grain: One row per Security per Trading Day
   ========================================================= */

CREATE TABLE dbo.FactPrices_Daily
(
    PriceID BIGINT IDENTITY(1,1) NOT NULL,
    SecurityID INT NOT NULL,
    TradeDate DATE NOT NULL,
    [Open] DECIMAL(18,4) NOT NULL,
    High DECIMAL(18,4) NOT NULL,
    Low DECIMAL(18,4) NOT NULL,
    [Close] DECIMAL(18,4) NOT NULL,
    AdjustedClose DECIMAL(18,4) NULL,
    Volume BIGINT NULL,

    CONSTRAINT PK_FactPrices_Daily
        PRIMARY KEY (PriceID),

    CONSTRAINT FK_FactPrices_Daily_DimSecurity
        FOREIGN KEY (SecurityID)
        REFERENCES dbo.DimSecurity(SecurityID),

    CONSTRAINT UQ_FactPrices_Daily_Security_Date
        UNIQUE (SecurityID, TradeDate)
);
GO