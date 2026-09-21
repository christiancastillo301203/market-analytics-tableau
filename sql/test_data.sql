SELECT
    COUNT(*) AS TotalRows,
    COUNT(DISTINCT Symbol) AS Securities,
    MIN(TradeDate) AS FirstDate,
    MAX(TradeDate) AS LastDate
FROM dbo.vHistoricalPricesReporting;
SELECT TOP 20 *
FROM dbo.vHistoricalPricesReporting
ORDER BY Symbol, TradeDate;