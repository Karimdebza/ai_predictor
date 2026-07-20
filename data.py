import logging
import time

import requests
import pandas as pd
from dotenv import load_dotenv

import config

logger = logging.getLogger(__name__)
load_dotenv()

FX_RETRY_ATTEMPTS = 3
FX_RETRY_BACKOFF_SECONDS = 1.5


def get_fix_history(to_currency, start_date, end_date):
    url = "https://api.frankfurter.dev/v2/rates"
    params = {
        "from": start_date.strftime("%Y-%m-%d"),
        "to": end_date.strftime("%Y-%m-%d"),
        "base": "EUR",
        "quotes": to_currency,
    }

    last_error = None
    resp = None
    for attempt in range(1, FX_RETRY_ATTEMPTS + 1):
        try:
            resp = requests.get(url, params=params, timeout=config.FX_API_TIMEOUT)
            resp.raise_for_status()
            last_error = None
            break
        except requests.RequestException as e:
            last_error = e
            logger.warning(
                "Appel à l'API Frankfurter échoué (tentative %d/%d) : %s",
                attempt, FX_RETRY_ATTEMPTS, e,
            )
            if attempt < FX_RETRY_ATTEMPTS:
                time.sleep(FX_RETRY_BACKOFF_SECONDS * attempt)

    if last_error is not None:
        logger.error("Appel à l'API Frankfurter définitivement échoué : %s", last_error)
        raise RuntimeError("Service de taux de change indisponible") from last_error

    data = resp.json()
    logger.debug("Frankfurter response sample: %s", data[:2] if isinstance(data, list) else data)

    if not isinstance(data, list) or len(data) == 0:
        raise RuntimeError("Pas de données FX")

    df = pd.DataFrame(data)
    df["date"] = pd.to_datetime(df["date"])
    df = df.rename(columns={"rate": "eur_to"})
    return df[["date", "eur_to"]].sort_values("date").reset_index(drop=True)


def get_oil_price_history(start_date, end_date):
    """Cours du Brent (USD/baril) via FRED — utilisé comme régresseur macro.
    Retourne un DataFrame vide si la clé est absente ou l'appel échoue :
    l'appelant doit dégrader proprement plutôt que planter la prédiction."""
    if not config.FRED_API_KEY:
        logger.warning("FRED_API_KEY absente — régresseur oil_price désactivé.")
        return pd.DataFrame(columns=["date", "oil_price"])

    url = "https://api.stlouisfed.org/fred/series/observations"
    params = {
        "series_id": "DCOILBRENTEU",
        "api_key": config.FRED_API_KEY,
        "file_type": "json",
        "observation_start": start_date.strftime("%Y-%m-%d"),
        "observation_end": end_date.strftime("%Y-%m-%d"),
    }

    try:
        resp = requests.get(url, params=params, timeout=config.FX_API_TIMEOUT)
        resp.raise_for_status()
        observations = resp.json()["observations"]
    except (requests.RequestException, KeyError, ValueError) as e:
        logger.warning("Appel FRED (oil_price) échoué : %s — régresseur désactivé.", e)
        return pd.DataFrame(columns=["date", "oil_price"])

    df = pd.DataFrame(observations)
    if df.empty:
        return pd.DataFrame(columns=["date", "oil_price"])

    df["date"] = pd.to_datetime(df["date"])
    # FRED utilise "." pour les valeurs manquantes (jours fériés US)
    df["oil_price"] = pd.to_numeric(df["value"], errors="coerce")
    return df[["date", "oil_price"]]
