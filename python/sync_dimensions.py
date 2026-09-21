from pathlib import Path
import os
import time

import pandas as pd
import requests
import pyodbc

from dotenv import load_dotenv


# ============================================================
# 1. LOCATE PROJECT FILES
# ============================================================

project_root = Path(__file__).resolve().parents[1]

config_path = (
    project_root
    / "config"
    / "security_universe.csv"
)


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
        f"Missing required columns: "
        f"{missing_columns}"
    )


duplicate_count = universe_df.duplicated(
    subset=[
        "Symbol",
        "ExchangeCode"
    ]
).sum()


if duplicate_count > 0:

    raise ValueError(
        "Duplicate Symbol + ExchangeCode "
        "combinations found."
    )


print(
    "Number of securities:",
    len(universe_df)
)

print(
    "Duplicate securities:",
    duplicate_count
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

print(
    "Connected to MarketAnalytics."
)


# ============================================================
# 5. EXCHANGE NAME MAPPING
# ============================================================

exchange_names = {
    "XNGS": "Nasdaq Global Select Market",
    "XNAS": "Nasdaq Stock Market",
    "XNYS": "New York Stock Exchange",
    "ARCX": "NYSE Arca"
}


# ============================================================
# 6. FUNCTION: GET SECURITY METADATA
# ============================================================

def get_security_metadata(
    symbol,
    exchange_code
):

    url = (
        "https://api.twelvedata.com/"
        "symbol_search"
    )

    params = {
        "symbol": symbol
    }

    headers = {
        "Authorization":
            f"apikey {api_key}"
    }

    response = requests.get(
        url,
        params=params,
        headers=headers,
        timeout=30
    )

    response.raise_for_status()

    data = response.json()


    if data.get("status") == "error":

        print(
            f"API error for {symbol}: "
            f"{data.get('message')}"
        )

        return None


    matches = data.get(
        "data",
        []
    )


    for item in matches:

        api_symbol = item.get(
            "symbol",
            ""
        ).upper()

        api_exchange = item.get(
            "exchange",
            ""
        ).upper()

        api_country = item.get(
            "country",
            ""
        ).upper()


        if (
            api_symbol
            == symbol.upper()

            and api_exchange
            == exchange_code.upper()

            and api_country
            == "UNITED STATES"
        ):

            return item


    available_markets = sorted(
        {
            (
                item.get("exchange"),
                item.get("mic_code"),
                item.get("country")
            )

            for item in matches

            if item.get(
                "symbol",
                ""
            ).upper()
            == symbol.upper()
        }
    )


    print(
        f"No exact match for {symbol} "
        f"on {exchange_code}. "
        f"Available markets: "
        f"{available_markets}"
    )

    return None


# ============================================================
# 7. FUNCTION: UPSERT EXCHANGE
# ============================================================

def upsert_exchange(metadata):

    exchange_code = metadata.get(
        "exchange"
    )

    mic = metadata.get(
        "mic_code"
    )

    country = metadata.get(
        "country"
    )

    currency = metadata.get(
        "currency"
    )

    timezone = metadata.get(
        "exchange_timezone"
    )


    if mic is None:

        raise ValueError(
            "MIC was not returned "
            f"for {metadata.get('symbol')}."
        )


    exchange_name = exchange_names.get(
        mic,
        exchange_code
    )


    # --------------------------------------------------------
    # Look for existing exchange by MIC
    # --------------------------------------------------------

    cursor.execute(
        """
        SELECT ExchangeID
        FROM dbo.DimExchange
        WHERE MIC = ?;
        """,
        mic
    )


    row = cursor.fetchone()


    # --------------------------------------------------------
    # Existing exchange -> UPDATE
    # --------------------------------------------------------

    if row is not None:

        exchange_id = row[0]


        cursor.execute(
            """
            UPDATE dbo.DimExchange

            SET
                ExchangeCode = ?,
                ExchangeName = ?,
                Country =
                    COALESCE(?, Country),
                Currency =
                    COALESCE(?, Currency),
                TimeZone =
                    COALESCE(?, TimeZone)

            WHERE ExchangeID = ?;
            """,
            exchange_code,
            exchange_name,
            country,
            currency,
            timezone,
            exchange_id
        )


        return exchange_id


    # --------------------------------------------------------
    # New exchange -> INSERT
    # --------------------------------------------------------

    cursor.execute(
        """
        INSERT INTO dbo.DimExchange
        (
            ExchangeCode,
            ExchangeName,
            MIC,
            Country,
            Currency,
            TimeZone
        )

        OUTPUT INSERTED.ExchangeID

        VALUES
        (
            ?, ?, ?, ?, ?, ?
        );
        """,
        exchange_code,
        exchange_name,
        mic,
        country,
        currency,
        timezone
    )


    exchange_id = (
        cursor.fetchone()[0]
    )


    return exchange_id


# ============================================================
# 8. FUNCTION: UPSERT SECURITY
# ============================================================

def upsert_security(
    metadata,
    exchange_id,
    sector=None,
    industry=None
):

    symbol = metadata.get(
        "symbol"
    )


    company_name = (
        metadata.get(
            "instrument_name"
        )
        or symbol
    )


    asset_type = metadata.get(
        "instrument_type"
    )


    trading_currency = metadata.get(
        "currency"
    )


    # --------------------------------------------------------
    # For our curated US universe, Symbol identifies
    # the primary security we want to track.
    #
    # This also lets us correct an old ExchangeID if
    # metadata changes during development.
    # --------------------------------------------------------

    cursor.execute(
        """
        SELECT SecurityID
        FROM dbo.DimSecurity
        WHERE Symbol = ?;
        """,
        symbol
    )


    row = cursor.fetchone()


    # --------------------------------------------------------
    # Existing security -> UPDATE
    # --------------------------------------------------------

    if row is not None:

        security_id = row[0]


        cursor.execute(
            """
            UPDATE dbo.DimSecurity

            SET
                ExchangeID = ?,
                CompanyName = ?,
                AssetType =
                    COALESCE(
                        ?,
                        AssetType
                    ),
                Sector =
                    COALESCE(
                        ?,
                        Sector
                    ),
                Industry =
                    COALESCE(
                        ?,
                        Industry
                    ),
                TradingCurrency =
                    COALESCE(
                        ?,
                        TradingCurrency
                    )

            WHERE SecurityID = ?;
            """,
            exchange_id,
            company_name,
            asset_type,
            sector,
            industry,
            trading_currency,
            security_id
        )


        return security_id


    # --------------------------------------------------------
    # New security -> INSERT
    # --------------------------------------------------------

    cursor.execute(
        """
        INSERT INTO dbo.DimSecurity
        (
            ExchangeID,
            Symbol,
            CompanyName,
            AssetType,
            Sector,
            Industry,
            TradingCurrency
        )

        OUTPUT INSERTED.SecurityID

        VALUES
        (
            ?, ?, ?, ?, ?, ?, ?
        );
        """,
        exchange_id,
        symbol,
        company_name,
        asset_type,
        sector,
        industry,
        trading_currency
    )


    security_id = (
        cursor.fetchone()[0]
    )


    return security_id


# ============================================================
# 9. PROCESS SECURITY UNIVERSE
# ============================================================

success_count = 0
failure_count = 0


for index, security in enumerate(
    universe_df.itertuples(
        index=False
    )
):

    symbol = security.Symbol

    exchange_code = (
        security.ExchangeCode
    )


    sector = getattr(
        security,
        "Sector",
        None
    )


    industry = getattr(
        security,
        "Industry",
        None
    )


    if pd.isna(sector):
        sector = None

    if pd.isna(industry):
        industry = None


    print(
        f"\nProcessing "
        f"{symbol} - "
        f"{exchange_code}"
    )


    try:

        metadata = (
            get_security_metadata(
                symbol,
                exchange_code
            )
        )


        if metadata is None:

            failure_count += 1


        else:

            mic = metadata.get(
                "mic_code"
            )


            exchange_id = (
                upsert_exchange(
                    metadata
                )
            )


            security_id = (
                upsert_security(
                    metadata,
                    exchange_id,
                    sector,
                    industry
                )
            )


            connection.commit()


            print(
                f"Saved {symbol} | "
                f"MIC={mic} | "
                f"ExchangeID="
                f"{exchange_id} | "
                f"SecurityID="
                f"{security_id}"
            )


            success_count += 1


    except Exception as error:

        connection.rollback()

        failure_count += 1

        print(
            f"ERROR processing "
            f"{symbol}: {error}"
        )


    # --------------------------------------------------------
    # Respect API rate limit
    # --------------------------------------------------------

    if index < len(universe_df) - 1:

        time.sleep(8)


# ============================================================
# 10. SUMMARY
# ============================================================

print(
    "\n================================"
)

print(
    "DIMENSION SYNC COMPLETE"
)

print(
    "================================"
)

print(
    "Successful:",
    success_count
)

print(
    "Failed:",
    failure_count
)


# ============================================================
# 11. CLOSE CONNECTION
# ============================================================

cursor.close()
connection.close()

print(
    "Connection closed."
)