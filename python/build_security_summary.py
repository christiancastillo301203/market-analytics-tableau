import pyodbc
import pandas as pd
import numpy as np


# ============================================================
# 1. SQL SERVER CONNECTION
# ============================================================

connection_string = (
    "DRIVER={ODBC Driver 18 for SQL Server};"
    "SERVER=localhost;"
    "DATABASE=MarketAnalytics;"
    "Trusted_Connection=yes;"
    "TrustServerCertificate=yes;"
)

connection = pyodbc.connect(connection_string)
cursor = connection.cursor()

print("Connected to MarketAnalytics.")


# ============================================================
# 2. EXTRACT HISTORICAL DATA
# ============================================================

query = """
SELECT
    fpd.SecurityID,
    ds.Symbol,
    ds.CompanyName,
    ds.Sector,
    ds.AssetType,
    de.ExchangeCode,
    fpd.TradeDate,
    fpd.AdjustedClose
FROM dbo.FactPrices_Daily AS fpd

INNER JOIN dbo.DimSecurity AS ds
    ON fpd.SecurityID = ds.SecurityID

INNER JOIN dbo.DimExchange AS de
    ON ds.ExchangeID = de.ExchangeID

ORDER BY
    ds.Symbol,
    fpd.TradeDate;
"""

cursor.execute(query)

columns = [column[0] for column in cursor.description]
rows = cursor.fetchall()

prices_df = pd.DataFrame.from_records(
    rows,
    columns=columns
)

print(f"Historical rows extracted: {len(prices_df):,}")
print(
    f"Securities found: "
    f"{prices_df['Symbol'].nunique()}"
)


# ============================================================
# 3. CLEAN DATA TYPES
# ============================================================

prices_df["TradeDate"] = pd.to_datetime(
    prices_df["TradeDate"]
)

prices_df["AdjustedClose"] = pd.to_numeric(
    prices_df["AdjustedClose"],
    errors="coerce"
)

prices_df = (
    prices_df
    .dropna(
        subset=[
            "Symbol",
            "TradeDate",
            "AdjustedClose"
        ]
    )
    .sort_values(
        ["Symbol", "TradeDate"]
    )
    .reset_index(drop=True)
)

if (prices_df["AdjustedClose"] <= 0).any():
    raise ValueError(
        "AdjustedClose contains zero or negative values."
    )


# ============================================================
# 4. PREPARE SPY BENCHMARK SERIES
# ============================================================

spy_df = (
    prices_df[
        prices_df["Symbol"] == "SPY"
    ][
        ["TradeDate", "AdjustedClose"]
    ]
    .drop_duplicates(
        subset=["TradeDate"]
    )
    .sort_values("TradeDate")
    .set_index("TradeDate")
)

if spy_df.empty:
    raise ValueError(
        "SPY was not found. "
        "SPY is required as the benchmark."
    )


# ============================================================
# 5. CALCULATE SECURITY-LEVEL METRICS
# ============================================================

summary_records = []

for symbol, security_df in prices_df.groupby("Symbol"):

    security_df = (
        security_df
        .sort_values("TradeDate")
        .reset_index(drop=True)
        .copy()
    )

    # --------------------------------------------------------
    # Basic security information
    # --------------------------------------------------------

    security_id = int(
        security_df["SecurityID"].iloc[0]
    )

    company_name = (
        security_df["CompanyName"].iloc[0]
    )

    sector = security_df["Sector"].iloc[0]

    asset_type = (
        security_df["AssetType"].iloc[0]
    )

    exchange_code = (
        security_df["ExchangeCode"].iloc[0]
    )

    # SPY is an ETF, so it does not have a corporate sector.
    if symbol == "SPY":
        sector_display = "Benchmark"
    elif pd.isna(sector):
        sector_display = "Other"
    else:
        sector_display = sector

    # --------------------------------------------------------
    # Beginning / ending information
    # --------------------------------------------------------

    first_date = security_df["TradeDate"].iloc[0]
    last_date = security_df["TradeDate"].iloc[-1]

    first_price = float(
        security_df["AdjustedClose"].iloc[0]
    )

    last_price = float(
        security_df["AdjustedClose"].iloc[-1]
    )

    price_rows = len(security_df)

    # --------------------------------------------------------
    # Total Return
    # --------------------------------------------------------

    total_return = (
        last_price / first_price
    ) - 1

    # --------------------------------------------------------
    # CAGR
    # --------------------------------------------------------

    days = (
        last_date - first_date
    ).days

    if days <= 0:
        cagr = np.nan
    else:
        cagr = (
            (last_price / first_price)
            ** (365.25 / days)
        ) - 1

    # --------------------------------------------------------
    # Daily Returns
    # --------------------------------------------------------

    security_df["DailyReturn"] = (
        security_df["AdjustedClose"]
        .pct_change()
    )

    daily_returns = (
        security_df["DailyReturn"]
        .dropna()
    )

    # --------------------------------------------------------
    # Annualized Volatility
    # --------------------------------------------------------

    if len(daily_returns) > 1:
        annualized_volatility = (
            daily_returns.std(ddof=1)
            * np.sqrt(252)
        )
    else:
        annualized_volatility = np.nan

    # --------------------------------------------------------
    # Maximum Drawdown
    # --------------------------------------------------------

    running_peak = (
        security_df["AdjustedClose"]
        .cummax()
    )

    drawdown = (
        security_df["AdjustedClose"]
        / running_peak
        - 1
    )

    maximum_drawdown = drawdown.min()

    # --------------------------------------------------------
    # Relative Performance vs SPY
    #
    # Uses SPY over the SAME beginning and ending dates
    # whenever those dates are available.
    # --------------------------------------------------------

    if symbol == "SPY":

        relative_performance_vs_spy = 0.0

    else:

        try:

            spy_first_price = float(
                spy_df.loc[
                    first_date,
                    "AdjustedClose"
                ]
            )

            spy_last_price = float(
                spy_df.loc[
                    last_date,
                    "AdjustedClose"
                ]
            )

            security_growth = (
                last_price / first_price
            )

            spy_growth = (
                spy_last_price
                / spy_first_price
            )

            relative_performance_vs_spy = (
                security_growth
                / spy_growth
                - 1
            )

        except KeyError:

            relative_performance_vs_spy = np.nan

    # --------------------------------------------------------
    # Store summary row
    # --------------------------------------------------------

    summary_records.append(
        {
            "SecurityID": security_id,
            "Symbol": symbol,
            "CompanyName": company_name,
            "Sector": sector,
            "SectorDisplay": sector_display,
            "AssetType": asset_type,
            "ExchangeCode": exchange_code,
            "FirstTradeDate": first_date.date(),
            "LastTradeDate": last_date.date(),
            "PriceRows": price_rows,
            "FirstAdjustedClose": first_price,
            "CurrentAdjustedPrice": last_price,
            "TotalReturn": total_return,
            "CAGR": cagr,
            "AnnualizedVolatility":
                annualized_volatility,
            "MaximumDrawdown":
                maximum_drawdown,
            "RelativePerformanceVsSPY":
                relative_performance_vs_spy
        }
    )


summary_df = pd.DataFrame(summary_records)

summary_df = (
    summary_df
    .sort_values("Symbol")
    .reset_index(drop=True)
)


# ============================================================
# 6. VALIDATE SUMMARY
# ============================================================

print("\nSecurity Summary Preview:\n")

print(
    summary_df[
        [
            "Symbol",
            "CAGR",
            "AnnualizedVolatility",
            "MaximumDrawdown",
            "RelativePerformanceVsSPY"
        ]
    ]
)

print(
    "\nSummary securities:",
    len(summary_df)
)

if summary_df["SecurityID"].duplicated().any():
    raise ValueError(
        "Duplicate SecurityID found in summary."
    )

if summary_df["Symbol"].duplicated().any():
    raise ValueError(
        "Duplicate Symbol found in summary."
    )

if len(summary_df) != prices_df["Symbol"].nunique():
    raise ValueError(
        "Summary security count does not "
        "match historical data."
    )


# ============================================================
# 7. CREATE SQL SUMMARY TABLE
# ============================================================

create_table_sql = """
IF OBJECT_ID(
    'dbo.SecuritySummary',
    'U'
) IS NULL

BEGIN

    CREATE TABLE dbo.SecuritySummary
    (
        SecurityID INT NOT NULL,

        Symbol VARCHAR(20) NOT NULL,

        CompanyName VARCHAR(200) NOT NULL,

        Sector VARCHAR(100) NULL,

        SectorDisplay VARCHAR(100) NOT NULL,

        AssetType VARCHAR(50) NULL,

        ExchangeCode VARCHAR(20) NULL,

        FirstTradeDate DATE NOT NULL,

        LastTradeDate DATE NOT NULL,

        PriceRows INT NOT NULL,

        FirstAdjustedClose DECIMAL(18,4) NOT NULL,

        CurrentAdjustedPrice DECIMAL(18,4) NOT NULL,

        TotalReturn DECIMAL(18,8) NULL,

        CAGR DECIMAL(18,8) NULL,

        AnnualizedVolatility DECIMAL(18,8) NULL,

        MaximumDrawdown DECIMAL(18,8) NULL,

        RelativePerformanceVsSPY DECIMAL(18,8) NULL,

        CONSTRAINT PK_SecuritySummary
            PRIMARY KEY (SecurityID),

        CONSTRAINT UQ_SecuritySummary_Symbol
            UNIQUE (Symbol),

        CONSTRAINT FK_SecuritySummary_DimSecurity
            FOREIGN KEY (SecurityID)
            REFERENCES dbo.DimSecurity(SecurityID)
    );

END;
"""

cursor.execute(create_table_sql)
connection.commit()

print(
    "\ndbo.SecuritySummary table ready."
)


# ============================================================
# 8. REFRESH SUMMARY TABLE
# ============================================================

cursor.execute(
    "DELETE FROM dbo.SecuritySummary;"
)

insert_sql = """
INSERT INTO dbo.SecuritySummary
(
    SecurityID,
    Symbol,
    CompanyName,
    Sector,
    SectorDisplay,
    AssetType,
    ExchangeCode,
    FirstTradeDate,
    LastTradeDate,
    PriceRows,
    FirstAdjustedClose,
    CurrentAdjustedPrice,
    TotalReturn,
    CAGR,
    AnnualizedVolatility,
    MaximumDrawdown,
    RelativePerformanceVsSPY
)
VALUES
(
    ?, ?, ?, ?, ?, ?, ?, ?, ?,
    ?, ?, ?, ?, ?, ?, ?, ?
);
"""

for row in summary_df.itertuples(index=False):

    cursor.execute(
        insert_sql,
        int(row.SecurityID),
        row.Symbol,
        row.CompanyName,
        None
        if pd.isna(row.Sector)
        else row.Sector,
        row.SectorDisplay,
        None
        if pd.isna(row.AssetType)
        else row.AssetType,
        None
        if pd.isna(row.ExchangeCode)
        else row.ExchangeCode,
        row.FirstTradeDate,
        row.LastTradeDate,
        int(row.PriceRows),
        float(row.FirstAdjustedClose),
        float(row.CurrentAdjustedPrice),
        None
        if pd.isna(row.TotalReturn)
        else float(row.TotalReturn),
        None
        if pd.isna(row.CAGR)
        else float(row.CAGR),
        None
        if pd.isna(row.AnnualizedVolatility)
        else float(row.AnnualizedVolatility),
        None
        if pd.isna(row.MaximumDrawdown)
        else float(row.MaximumDrawdown),
        None
        if pd.isna(row.RelativePerformanceVsSPY)
        else float(row.RelativePerformanceVsSPY)
    )

connection.commit()

print(
    f"Rows loaded into SecuritySummary: "
    f"{len(summary_df)}"
)


# ============================================================
# 9. VERIFY SQL RESULTS
# ============================================================

verification_sql = """
SELECT
    Symbol,
    CAGR,
    AnnualizedVolatility,
    MaximumDrawdown,
    RelativePerformanceVsSPY
FROM dbo.SecuritySummary
ORDER BY CAGR DESC;
"""

cursor.execute(verification_sql)

verification_rows = cursor.fetchall()

print("\nSQL Security Summary:\n")

for row in verification_rows:
    print(row)



# ============================================================
# 10. EXPORT SUMMARY FOR TABLEAU PUBLIC
# ============================================================

from pathlib import Path

project_root = Path(__file__).resolve().parents[1]

output_dir = project_root / "output"
output_dir.mkdir(exist_ok=True)

output_path = output_dir / "security_summary.csv"

summary_df.to_csv(
    output_path,
    index=False
)

print("\nTableau summary export complete.")
print("File:", output_path)
print("Rows:", len(summary_df))

# ============================================================
# 11. CLOSE CONNECTION
# ============================================================

cursor.close()
connection.close()

print("\n================================")
print("SECURITY SUMMARY BUILD COMPLETE")
print("================================")
print(
    f"Securities: {len(summary_df)}"
)
print("Connection closed.")