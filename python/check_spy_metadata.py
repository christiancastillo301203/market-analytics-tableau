from pathlib import Path
import os

import requests
from dotenv import load_dotenv


# Find project root
project_root = Path(__file__).resolve().parents[1]

# Load API key
load_dotenv(project_root / ".env")

api_key = os.getenv("TWELVE_DATA_API_KEY")


# Request SPY metadata
url = "https://api.twelvedata.com/symbol_search"

params = {
    "symbol": "SPY"
}

headers = {
    "Authorization": f"apikey {api_key}"
}

response = requests.get(
    url,
    params=params,
    headers=headers,
    timeout=30
)

data = response.json()


# Show every exact SPY match
print("\nSPY matches:\n")

for item in data.get("data", []):

    if item.get("symbol") == "SPY":

        print(
            "Exchange:",
            item.get("exchange"),
            "| MIC:",
            item.get("mic_code"),
            "| Country:",
            item.get("country"),
            "| Currency:",
            item.get("currency"),
            "| Type:",
            item.get("instrument_type")
        )