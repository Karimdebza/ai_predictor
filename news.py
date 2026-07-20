import logging
import time

import requests

import config

logger = logging.getLogger(__name__)

GDELT_URL = "https://api.gdeltproject.org/api/v2/doc/doc"

# GDELT demande explicitement max 1 requête / 5s côté client public.
# On le respecte nous-mêmes en plus du cache Redis (cache.py) qui absorbe
# l'essentiel du trafic de nos propres utilisateurs.
_MIN_INTERVAL_SECONDS = 5.0
_last_call_at = 0.0

DEVISE_KEYWORDS = {
    "MAD": ["Morocco", "Maroc", "dirham", "Bank Al-Maghrib"],
    "USD": ["Federal Reserve", "US dollar", "United States economy"],
    "GBP": ["Bank of England", "British pound", "UK economy"],
    "JPY": ["Bank of Japan", "yen", "Japan economy"],
    "VND": ["Vietnam", "dong", "State Bank of Vietnam"],
}

SHOCK_KEYWORDS = [
    "war", "conflict", "sanctions", "oil price", "invasion",
    "central bank emergency", "market crash", "crisis",
]


def _build_query(devise: str) -> str:
    devise_terms = DEVISE_KEYWORDS.get(devise, [devise])
    devise_clause = " OR ".join(f'"{t}"' if " " in t else t for t in devise_terms)
    shock_clause = " OR ".join(f'"{t}"' if " " in t else t for t in SHOCK_KEYWORDS)
    return f"({devise_clause}) ({shock_clause})"


def fetch_alerts(devise: str, max_records: int = 5, timespan: str = "2d"):
    """Récupère les articles d'actu récents liés à la devise + un choc potentiel.
    Ne lève jamais d'exception : dégrade en liste vide si GDELT est indisponible
    ou rate-limite, pour ne jamais casser l'endpoint appelant."""
    global _last_call_at

    elapsed = time.monotonic() - _last_call_at
    if elapsed < _MIN_INTERVAL_SECONDS:
        time.sleep(_MIN_INTERVAL_SECONDS - elapsed)

    params = {
        "query": _build_query(devise),
        "mode": "artlist",
        "maxrecords": max_records,
        "format": "json",
        "timespan": timespan,
        "sort": "DateDesc",
    }

    try:
        _last_call_at = time.monotonic()
        resp = requests.get(GDELT_URL, params=params, timeout=config.FX_API_TIMEOUT)
        resp.raise_for_status()
        data = resp.json()
    except (requests.RequestException, ValueError) as e:
        logger.warning("Appel GDELT échoué pour %s : %s — alertes désactivées.", devise, e)
        return []

    articles = data.get("articles", [])
    if not isinstance(articles, list):
        logger.warning("Réponse GDELT inattendue pour %s : %r", devise, data)
        return []

    return [
        {
            "title": a.get("title"),
            "url": a.get("url"),
            "source": a.get("domain"),
            "seendate": a.get("seendate"),
        }
        for a in articles
        if a.get("title") and a.get("url")
    ]
