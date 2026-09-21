from pathlib import Path
from datetime import date, timedelta
import os
import time

import pandas as pd
import requests
import pyodbc

from dotenv import load_dotenv


# ============================================================
# 1. PROJECT CONFIGURATION
# ============================================================

project_root = Path(__file__).resolve().parents[1]

config_path = (
    project_root
    / "config"
    / "security_universe.csv"
)

history_start_date = date(2019, 1, 1)

history_end_date = date.today()

request_pause_seconds = 8


# ============================================================
# 2. LOAD API KEY
# ============================================================

load_dotenv(project_root / ".env")

api_key = os.getenv("TWELVE_DATA_API_KEY")

if api_key is None:
    raise ValueError(
        "TWELVE_DATA_API_KEY was not found."
    )


# ============================================================
# 3. READ SECURITY UNIVERSE
# ============================================================

universe_df = pd.read_csv(config_path)

required_columns = {
    "Symbol",
    "ExchangeCode"
}

missing_columns = (
    required_columns
    - set(universe_df.columns)
)

if missing_columns:
    raise ValueError(
        f"Missing required columns: {missing_columns}"
    )


duplicate_count = universe_df.duplicated(
    subset=["Symbol"]
).sum()

if duplicate_count > 0:
    raise ValueError(
        "Duplicate symbols were found "
        "in security_universe.csv."
    )


print(
    "Securities to process:",
    len(universe_df)
)

print(
    "Historical start date:",
    history_start_date
)

print(
    "Historical end date:",
    history_end_date
)


# ============================================================
# 4. SQL SERVER CONNECTION
# ============================================================

connection_string = (
    "DRIVER={ODBC Driver 18 for SQL Server};"
    "SERVER=localhost;"
    "DATABASE=MarketAnalytics;"
    "Trusted_Connection=yes;"
    "TrustServerCertificate=yes;"
)

connection = pyodbc.connect(
    connection_string
)

cursor = connection.cursor()

cursor.fast_executemany = True

print(
    "Connected to MarketAnalytics."
)


# ============================================================
# 5. FIND SECURITY ID
# ============================================================

def get_security_id(symbol):

    cursor.execute(
        """
        SELECT SecurityID
        FROM dbo.DimSecurity
        WHERE Symbol = ?;
        """,
        symbol
    )

    rows = cursor.fetchall()


    if len(rows) == 0:

        raise ValueError(
            f"{symbol} was not found "
            f"in DimSecurity."
        )


    if len(rows) > 1:

        raise ValueError(
            f"More than one SecurityID "
            f"was found for {symbol}."
        )


    return rows[0][0]


# ============================================================
# 6. FIND LAST DATE ALREADY LOADED
# ============================================================

def get_last_trade_date(security_id):

    cursor.execute(
        """
        SELECT MAX(TradeDate)
        FROM dbo.FactPrices_Daily
        WHERE SecurityID = ?;
        """,
        security_id
    )

    row = cursor.fetchone()

    return row[0]


# ============================================================
# 7. TWELVE DATA REQUEST
# ============================================================

def request_time_series(
    symbol,
    start_date,
    end_date,
    adjust
):

    url = (
        "https://api.twelvedata.com/"
        "time_series"
    )

    params = {
        "symbol": symbol,
        "interval": "1day",
        "start_date": str(start_date),
        "end_date": str(end_date),
        "outputsize": 5000,
        "adjust": adjust
    }

    headers = {
        "Authorization":
            f"apikey {api_key}"
    }


    try:

        response = requests.get(
            url,
            params=params,
            headers=headers,
            timeout=30
        )


        try:
            data = response.json()

        except ValueError:

            response.raise_for_status()

            raise RuntimeError(
                f"Invalid response received "
                f"for {symbol}."
            )


        # --------------------------------------------
        # API returned an application-level error
        # --------------------------------------------

        if data.get("status") == "error":

            message = data.get(
                "message",
                "Unknown API error"
            )


            # No trading data in requested period
            if "no data" in message.lower():

                return []


            raise RuntimeError(
                f"Twelve Data error "
                f"for {symbol}: {message}"
            )


        response.raise_for_status()


        return data.get(
            "values",
            []
        )


    finally:

        # Pause after every API call
        time.sleep(
            request_pause_seconds
        )


# ============================================================
# 8. BUILD CLEAN PRICE DATAFRAME
# ============================================================

def build_price_dataframe(
    symbol,
    start_date,
    end_date
):

    # --------------------------------------------------------
    # RAW / UNADJUSTED PRICES
    # --------------------------------------------------------

    raw_values = request_time_series(
        symbol=symbol,
        start_date=start_date,
        end_date=end_date,
        adjust="none"
    )


    # No new trading data
    if len(raw_values) == 0:

        return pd.DataFrame()


    raw_df = pd.DataFrame(
        raw_values
    )


    required_price_columns = {
        "datetime",
        "open",
        "high",
        "low",
        "close",
        "volume"
    }


    missing_price_columns = (
        required_price_columns
        - set(raw_df.columns)
    )


    if missing_price_columns:

        raise ValueError(
            f"{symbol} raw data is missing "
            f"columns: "
            f"{missing_price_columns}"
        )


    # --------------------------------------------------------
    # CLEAN RAW DATA
    # --------------------------------------------------------

    raw_df["datetime"] = pd.to_datetime(
        raw_df["datetime"]
    )


    numeric_columns = [
        "open",
        "high",
        "low",
        "close",
        "volume"
    ]


    for column in numeric_columns:

        raw_df[column] = pd.to_numeric(
            raw_df[column],
            errors="coerce"
        )


    raw_df = raw_df.drop_duplicates(
        subset=["datetime"]
    )


    # --------------------------------------------------------
    # ADJUSTED PRICES
    # --------------------------------------------------------

    adjusted_values = request_time_series(
        symbol=symbol,
        start_date=start_date,
        end_date=end_date,
        adjust="all"
    )


    if len(adjusted_values) == 0:

        raise ValueError(
            f"No adjusted price data "
            f"was returned for {symbol}."
        )


    adjusted_df = pd.DataFrame(
        adjusted_values
    )


    if (
        "datetime" not in adjusted_df.columns
        or "close" not in adjusted_df.columns
    ):

        raise ValueError(
            f"Adjusted data for {symbol} "
            f"is missing required columns."
        )


    adjusted_df = adjusted_df[
        [
            "datetime",
            "close"
        ]
    ].copy()


    adjusted_df["datetime"] = (
        pd.to_datetime(
            adjusted_df["datetime"]
        )
    )


    adjusted_df["close"] = (
        pd.to_numeric(
            adjusted_df["close"],
            errors="coerce"
        )
    )


    adjusted_df = (
        adjusted_df
        .drop_duplicates(
            subset=["datetime"]
        )
        .rename(
            columns={
                "close":
                    "adjusted_close"
            }
        )
    )


    # --------------------------------------------------------
    # MERGE RAW + ADJUSTED
    # --------------------------------------------------------

    final_df = raw_df.merge(
        adjusted_df,
        on="datetime",
        how="left"
    )


    # --------------------------------------------------------
    # RENAME TO SQL COLUMN NAMES
    # --------------------------------------------------------

    final_df = final_df.rename(
        columns={
            "datetime": "TradeDate",
            "open": "Open",
            "high": "High",
            "low": "Low",
            "close": "Close",
            "volume": "Volume",
            "adjusted_close":
                "AdjustedClose"
        }
    )


    final_df["TradeDate"] = (
        final_df["TradeDate"]
        .dt.date
    )


    final_df = (
        final_df
        .sort_values("TradeDate")
        .reset_index(drop=True)
    )


    # ========================================================
    # DATA QUALITY CHECKS
    # ========================================================

    required_sql_columns = [
        "TradeDate",
        "Open",
        "High",
        "Low",
        "Close",
        "AdjustedClose",
        "Volume"
    ]


    missing_values = (
        final_df[
            required_sql_columns
        ]
        .isna()
        .sum()
        .sum()
    )


    if missing_values > 0:

        raise ValueError(
            f"{symbol} contains "
            f"{missing_values} missing values."
        )


    duplicate_dates = (
        final_df
        .duplicated(
            subset=["TradeDate"]
        )
        .sum()
    )


    if duplicate_dates > 0:

        raise ValueError(
            f"{symbol} contains "
            f"{duplicate_dates} "
            f"duplicate trading dates."
        )


    invalid_ohlc = final_df[
        (final_df["High"] < final_df["Low"])
        |
        (final_df["High"] < final_df["Open"])
        |
        (final_df["High"] < final_df["Close"])
        |
        (final_df["Low"] > final_df["Open"])
        |
        (final_df["Low"] > final_df["Close"])
    ]


    if not invalid_ohlc.empty:

        raise ValueError(
            f"{symbol} contains "
            f"invalid OHLC relationships."
        )


    price_columns = [
        "Open",
        "High",
        "Low",
        "Close",
        "AdjustedClose"
    ]


    if (
        final_df[
            price_columns
        ] <= 0
    ).any().any():

        raise ValueError(
            f"{symbol} contains "
            f"zero or negative prices."
        )


    if (
        final_df["Volume"] < 0
    ).any():

        raise ValueError(
            f"{symbol} contains "
            f"negative volume."
        )


    return final_df[
        required_sql_columns
    ]


# ============================================================
# 9. INSERT DATA INTO FACTPRICES_DAILY
# ============================================================

insert_query = """
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
"""


def insert_price_data(
    security_id,
    price_df
):

    records = []


    for row in price_df.itertuples(
        index=False
    ):

        records.append(
            (
                int(security_id),
                row.TradeDate,
                float(row.Open),
                float(row.High),
                float(row.Low),
                float(row.Close),
                float(row.AdjustedClose),
                int(row.Volume)
            )
        )


    if len(records) == 0:

        return 0


    cursor.executemany(
        insert_query,
        records
    )


    connection.commit()


    return len(records)


# ============================================================
# 10. PROCESS ENTIRE SECURITY UNIVERSE
# ============================================================

total_inserted = 0

success_count = 0
failure_count = 0
up_to_date_count = 0


for security in universe_df.itertuples(
    index=False
):

    symbol = (
        str(security.Symbol)
        .strip()
        .upper()
    )


    print(
        "\n================================"
    )

    print(
        f"Processing {symbol}"
    )

    print(
        "================================"
    )


    try:

        # ----------------------------------------------------
        # Find SecurityID
        # ----------------------------------------------------

        security_id = (
            get_security_id(
                symbol
            )
        )


        print(
            "SecurityID:",
            security_id
        )


        # ----------------------------------------------------
        # Determine incremental start date
        # ----------------------------------------------------

        last_trade_date = (
            get_last_trade_date(
                security_id
            )
        )


        if last_trade_date is None:

            start_date = (
                history_start_date
            )

            print(
                "Initial historical load."
            )


        else:

            start_date = (
                last_trade_date
                + timedelta(days=1)
            )

            print(
                "Last stored date:",
                last_trade_date
            )


        # ----------------------------------------------------
        # Nothing new to request
        # ----------------------------------------------------

        if start_date > history_end_date:

            print(
                f"{symbol} is already "
                f"up to date."
            )

            up_to_date_count += 1

            continue


        print(
            "Requesting:",
            start_date,
            "to",
            history_end_date
        )


        # ----------------------------------------------------
        # Extract + Transform + Validate
        # ----------------------------------------------------

        price_df = (
            build_price_dataframe(
                symbol=symbol,
                start_date=start_date,
                end_date=history_end_date
            )
        )


        # ----------------------------------------------------
        # No trading dates in requested period
        # ----------------------------------------------------

        if price_df.empty:

            print(
                f"No new trading data "
                f"for {symbol}."
            )

            up_to_date_count += 1

            continue


        print(
            "Validated rows:",
            len(price_df)
        )


        # ----------------------------------------------------
        # Load into SQL
        # ----------------------------------------------------

        inserted_rows = (
            insert_price_data(
                security_id,
                price_df
            )
        )


        print(
            "Inserted rows:",
            inserted_rows
        )


        total_inserted += (
            inserted_rows
        )

        success_count += 1


    except Exception as error:

        connection.rollback()

        failure_count += 1


        print(
            f"ERROR processing "
            f"{symbol}:"
        )

        print(
            error
        )


# ============================================================
# 11. FINAL SUMMARY
# ============================================================

print(
    "\n================================"
)

print(
    "PRICE HISTORY LOAD COMPLETE"
)

print(
    "================================"
)

print(
    "Successful securities:",
    success_count
)

print(
    "Already up to date:",
    up_to_date_count
)

print(
    "Failed securities:",
    failure_count
)

print(
    "Total rows inserted:",
    total_inserted
)


# ============================================================
# 12. DATABASE VALIDATION
# ============================================================

cursor.execute(
    """
    SELECT
        COUNT(*) AS TotalRows,
        COUNT(DISTINCT SecurityID) AS SecurityCount,
        MIN(TradeDate) AS FirstDate,
        MAX(TradeDate) AS LastDate
    FROM dbo.FactPrices_Daily;
    """
)


summary_row = cursor.fetchone()


print(
    "\nDatabase Summary:"
)

print(
    "Rows:",
    summary_row[0]
)

print(
    "Securities:",
    summary_row[1]
)

print(
    "First Date:",
    summary_row[2]
)

print(
    "Last Date:",
    summary_row[3]
)


# ============================================================
# 13. CLOSE CONNECTION
# ============================================================

cursor.close()
connection.close()

print(
    "\nConnection closed."
)