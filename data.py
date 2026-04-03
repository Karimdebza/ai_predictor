import requests
import pandas as pd
from dotenv import load_dotenv

load_dotenv()


def get_fix_history(to_currency, start_date, end_date):
    url = "https://api.frankfurter.dev/v2/rates"
    params = {
        "from": start_date.strftime("%Y-%m-%d"),
        "to": end_date.strftime("%Y-%m-%d"),
        "base": "EUR",
        "quotes": to_currency
    }

    resp = requests.get(url, params=params)
    if resp.status_code != 200:
        raise Exception(f"Frankfurter API ERROR {resp.status_code}: {resp.text[:200]}")

    data = resp.json()
    print("RAW DATA SAMPLE:", data[:2]) 
    if not isinstance(data, list) or len(data) == 0:
        raise Exception("Pas de données FX")

    df = pd.DataFrame(data)
    print("COLUMNS:", df.columns.tolist())
    df["date"] = pd.to_datetime(df["date"])
    df = df.rename(columns={"rate": "eur_to"})
    return df[["date", "eur_to"]].sort_values("date").reset_index(drop=True)