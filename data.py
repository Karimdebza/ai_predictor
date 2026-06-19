import logging

import requests
import pandas as pd
from dotenv import load_dotenv

import config

logger = logging.getLogger(__name__)
load_dotenv()


def get_fix_history(to_currency, start_date, end_date):
    url = "https://api.frankfurter.dev/v2/rates"
    params = {
        "from": start_date.strftime("%Y-%m-%d"),
        "to": end_date.strftime("%Y-%m-%d"),
        "base": "EUR",
        "quotes": to_currency,
    }

    try:
        resp = requests.get(url, params=params, timeout=config.FX_API_TIMEOUT)
        resp.raise_for_status()
    except requests.RequestException as e:
        logger.error("Appel à l'API Frankfurter échoué : %s", e)
        raise RuntimeError("Service de taux de change indisponible") from e

    data = resp.json()
    logger.debug("Frankfurter response sample: %s", data[:2] if isinstance(data, list) else data)

    if not isinstance(data, list) or len(data) == 0:
        raise RuntimeError("Pas de données FX")

    df = pd.DataFrame(data)
    df["date"] = pd.to_datetime(df["date"])
    df = df.rename(columns={"rate": "eur_to"})
    return df[["date", "eur_to"]].sort_values("date").reset_index(drop=True)
