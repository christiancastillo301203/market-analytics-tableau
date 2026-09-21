import pyodbc

from extract_market_data import final_df


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

print("Connected to SQL Server successfully.")


# ============================================================
# 2. SECURITY TO LOAD
# ============================================================

symbol = "AAPL"
exchange_code = "NASDAQ"


# ============================================================
# 3. FIND SECURITY ID
# ============================================================

security_query = """
SELECT
    sec.SecurityID
FROM dbo.DimSecurity AS sec

INNER JOIN dbo.DimExchange AS exc
    ON sec.ExchangeID = exc.ExchangeID

WHERE sec.Symbol = ?
    AND exc.ExchangeCode = ?;
"""

cursor.execute(
    security_query,
    symbol,
    exchange_code
)

row = cursor.fetchone()


if row is None:
    raise ValueError(
        f"{symbol} on {exchange_code} was not found in DimSecurity."
    )


security_id = row[0]

print("SecurityID found:", security_id)


# ============================================================
# 4. INSERT DAILY PRICES
# ============================================================

insert_query = """
IF NOT EXISTS
(
    SELECT 1
    FROM dbo.FactPrices_Daily
    WHERE SecurityID = ?
        AND TradeDate = ?
)
BEGIN

    INSERT INTO dbo.FactPrices_Daily
    (
        SecurityID,
        TradeDate,
        [Open],
        High,
        Low,
        [Close],
        AdjustedClose,
        Volume
    )

    VALUES
    (
        ?, ?, ?, ?, ?, ?, ?, ?
    );

END;
"""


rows_inserted = 0


for row in final_df.itertuples(index=False):

    cursor.execute(
        insert_query,

        # Values used by IF NOT EXISTS
        security_id,
        row.TradeDate,

        # Values inserted
        security_id,
        row.TradeDate,
        float(row.Open),
        float(row.High),
        float(row.Low),
        float(row.Close),
        float(row.AdjustedClose),
        int(row.Volume)
    )

    rows_inserted += 1


# ============================================================
# 5. SAVE CHANGES
# ============================================================

connection.commit()

print("Rows processed:", rows_inserted)


# ============================================================
# 6. VERIFY DATA IN SQL
# ============================================================

verification_query = """
SELECT
    SecurityID,
    TradeDate,
    [Open],
    High,
    Low,
    [Close],
    AdjustedClose,
    Volume
FROM dbo.FactPrices_Daily
WHERE SecurityID = ?
ORDER BY TradeDate;
"""

cursor.execute(
    verification_query,
    security_id
)

rows = cursor.fetchall()

print("\nRows currently stored in FactPrices_Daily:")

for row in rows:
    print(row)


# ============================================================
# 7. CLOSE CONNECTION
# ============================================================

cursor.close()
connection.close()

print("\nConnection closed.")