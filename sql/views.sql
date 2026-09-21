USE MarketAnalytics;
GO


CREATE OR ALTER VIEW dbo.vHistoricalPricesReporting
AS

SELECT
    /* =====================================================
       DATE
       ===================================================== */

    fpd.TradeDate,


    /* =====================================================
       PRICE DATA
       ===================================================== */

    fpd.[Open],
    fpd.High,
    fpd.Low,
    fpd.[Close],
    fpd.AdjustedClose,
    fpd.Volume,


    /* =====================================================
       SECURITY ATTRIBUTES
       ===================================================== */

    ds.SecurityID,
    ds.Symbol,
    ds.CompanyName,
    ds.AssetType,
    ds.Sector,
    ds.Industry,
    ds.TradingCurrency,


    /* =====================================================
       EXCHANGE ATTRIBUTES
       ===================================================== */

    de.ExchangeCode,
    de.ExchangeName,
    de.MIC,
    de.Country,
    de.TimeZone


FROM dbo.FactPrices_Daily AS fpd

INNER JOIN dbo.DimSecurity AS ds
    ON fpd.SecurityID = ds.SecurityID

INNER JOIN dbo.DimExchange AS de
    ON ds.ExchangeID = de.ExchangeID;
GO