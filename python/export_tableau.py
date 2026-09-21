from pathlib import Path

import pandas as pd
import pyodbc


# ============================================================
# 1. LOCATE PROJECT FOLDERS
# ============================================================

project_root = Path(__file__).resolve().parents[1]

output_folder = (
    project_root
    / "output"
)

output_folder.mkdir(
    exist_ok=True
)

output_path = (
    output_folder
    / "market_analytics_tableau.xlsx"
)


# ============================================================
# 2. SQL SERVER CONNECTION
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
# 3. READ REPORTING VIEW
# ============================================================

query = """
SELECT
    TradeDate,
    [Open],
    High,
    Low,
    [Close],
    AdjustedClose,
    Volume,
    SecurityID,
    Symbol,
    CompanyName,
    AssetType,
    Sector,
    Industry,
    TradingCurrency,
    ExchangeCode,
    ExchangeName,
    MIC,
    Country,
    TimeZone

FROM dbo.vHistoricalPricesReporting

ORDER BY
    Symbol,
    TradeDate;
"""


cursor.execute(query)

rows = cursor.fetchall()


columns = [
    column[0]
    for column in cursor.description
]


df = pd.DataFrame.from_records(
    rows,
    columns=columns
)


# ============================================================
# 4. VALIDATE EXTRACT
# ============================================================

print(
    "Rows extracted:",
    len(df)
)

print(
    "Securities:",
    df["Symbol"].nunique()
)

print(
    "First date:",
    df["TradeDate"].min()
)

print(
    "Last date:",
    df["TradeDate"].max()
)


if len(df) == 0:

    raise ValueError(
        "Reporting view returned no rows."
    )


if df["Symbol"].nunique() != 25:

    raise ValueError(
        "Expected 25 securities."
    )


# ============================================================
# 5. EXPORT TO EXCEL
# ============================================================

with pd.ExcelWriter(
    output_path,
    engine="xlsxwriter",
    datetime_format="yyyy-mm-dd",
    date_format="yyyy-mm-dd"
) as writer:

    # --------------------------------------------------------
    # Main Tableau dataset
    # --------------------------------------------------------

    df.to_excel(
        writer,
        sheet_name="HistoricalPrices",
        index=False
    )


    # --------------------------------------------------------
    # Basic extract information
    # --------------------------------------------------------

    summary_df = pd.DataFrame(
        {
            "Metric": [
                "Total Rows",
                "Securities",
                "First Date",
                "Last Date"
            ],

            "Value": [
                len(df),
                df["Symbol"].nunique(),
                df["TradeDate"].min(),
                df["TradeDate"].max()
            ]
        }
    )


    summary_df.to_excel(
        writer,
        sheet_name="ExtractSummary",
        index=False
    )


    # --------------------------------------------------------
    # Basic formatting
    # --------------------------------------------------------

    workbook = writer.book

    historical_sheet = (
        writer.sheets["HistoricalPrices"]
    )

    summary_sheet = (
        writer.sheets["ExtractSummary"]
    )


    header_format = (
        workbook.add_format(
            {
                "bold": True,
                "border": 1
            }
        )
    )


    for column_number, column_name in enumerate(
        df.columns
    ):

        historical_sheet.write(
            0,
            column_number,
            column_name,
            header_format
        )


    historical_sheet.freeze_panes(
        1,
        0
    )


    historical_sheet.autofilter(
        0,
        0,
        len(df),
        len(df.columns) - 1
    )


    historical_sheet.set_column(
        0,
        0,
        12
    )

    historical_sheet.set_column(
        1,
        6,
        14
    )

    historical_sheet.set_column(
        7,
        7,
        12
    )

    historical_sheet.set_column(
        8,
        8,
        12
    )

    historical_sheet.set_column(
        9,
        18,
        24
    )


    summary_sheet.set_column(
        0,
        0,
        20
    )

    summary_sheet.set_column(
        1,
        1,
        20
    )


# ============================================================
# 6. CLOSE SQL CONNECTION
# ============================================================

cursor.close()
connection.close()


# ============================================================
# 7. FINAL MESSAGE
# ============================================================

print(
    "\n================================"
)

print(
    "TABLEAU EXPORT COMPLETE"
)

print(
    "================================"
)

print(
    "File:",
    output_path
)

print(
    "Rows:",
    len(df)
)

print(
    "Securities:",
    df["Symbol"].nunique()
)

print(
    "\nConnection closed."
)