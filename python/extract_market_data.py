import os
import requests
import pandas as pd
from dotenv import load_dotenv


# ============================================================
# 1. LOAD API KEY
# ============================================================

load_dotenv()

api_key = os.getenv("TWELVE_DATA_API_KEY")


# ============================================================
# 2. API ENDPOINT
# ============================================================

url = "https://api.twelvedata.com/time_series"

headers = {
    "Authorization": f"apikey {api_key}"
}


# ============================================================
# 3. REQUEST RAW / UNADJUSTED PRICES
# ============================================================

raw_params = {
    "symbol": "AAPL",
    "interval": "1day",
    "outputsize": 5,
    "adjust": "none"
}

raw_response = requests.get(
    url,
    params=raw_params,
    headers=headers,
    timeout=30
)

print("Raw request status:", raw_response.status_code)

raw_data = raw_response.json()

raw_prices = raw_data["values"]

df = pd.DataFrame(raw_prices)


# ============================================================
# 4. CLEAN RAW DATA
# ============================================================

df["datetime"] = pd.to_datetime(df["datetime"])

df["open"] = pd.to_numeric(df["open"])
df["high"] = pd.to_numeric(df["high"])
df["low"] = pd.to_numeric(df["low"])
df["close"] = pd.to_numeric(df["close"])
df["volume"] = pd.to_numeric(df["volume"])

# Sort oldest date to newest date
df = df.sort_values("datetime").reset_index(drop=True)


# ============================================================
# 5. REQUEST ADJUSTED PRICES
# ============================================================

adjusted_params = {
    "symbol": "AAPL",
    "interval": "1day",
    "outputsize": 5,
    "adjust": "all"
}

adjusted_response = requests.get(
    url,
    params=adjusted_params,
    headers=headers,
    timeout=30
)

print("Adjusted request status:", adjusted_response.status_code)

adjusted_data = adjusted_response.json()

adjusted_prices = adjusted_data["values"]

adjusted_df = pd.DataFrame(adjusted_prices)


# ============================================================
# 6. KEEP ONLY DATE + ADJUSTED CLOSE
# ============================================================

adjusted_df = adjusted_df[["datetime", "close"]]

adjusted_df["datetime"] = pd.to_datetime(
    adjusted_df["datetime"]
)

adjusted_df["close"] = pd.to_numeric(
    adjusted_df["close"]
)

adjusted_df = adjusted_df.rename(
    columns={
        "close": "adjusted_close"
    }
)


# ============================================================
# 7. MERGE RAW + ADJUSTED DATA
# ============================================================

final_df = df.merge(
    adjusted_df,
    on="datetime",
    how="left"
)


# ============================================================
# 8. DISPLAY FINAL DATASET
# ============================================================

print("\nFinal DataFrame:")
print(final_df)

print("\nFinal Data Types:")
print(final_df.dtypes)

# ============================================================
# 9. RENAME COLUMNS TO MATCH SQL DATABASE
# ============================================================

final_df = final_df.rename(
    columns={
        "datetime": "TradeDate",
        "open": "Open",
        "high": "High",
        "low": "Low",
        "close": "Close",
        "volume": "Volume",
        "adjusted_close": "AdjustedClose"
    }
)

# SQL column is DATE, not DATETIME
final_df["TradeDate"] = final_df["TradeDate"].dt.date


# ============================================================
# 10. VALIDATE DATA
# ============================================================

print("\nMissing Values:")
print(final_df.isna().sum())

duplicate_count = final_df.duplicated(
    subset=["TradeDate"]
).sum()

print("\nDuplicate Dates:")
print(duplicate_count)


invalid_prices = final_df[
    (final_df["High"] < final_df["Low"]) |
    (final_df["High"] < final_df["Open"]) |
    (final_df["High"] < final_df["Close"]) |
    (final_df["Low"] > final_df["Open"]) |
    (final_df["Low"] > final_df["Close"])
]

print("\nInvalid OHLC Rows:")
print(invalid_prices)


invalid_volume = final_df[
    final_df["Volume"] < 0
]

print("\nInvalid Volume Rows:")
print(invalid_volume)


# ============================================================
# 11. DISPLAY SQL-READY DATASET
# ============================================================

print("\nSQL-Ready DataFrame:")
print(final_df)

print("\nSQL-Ready Data Types:")
print(final_df.dtypes)