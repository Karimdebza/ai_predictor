import logging
import re
import time
from datetime import datetime, timezone

import requests
import pandas as pd

import config

logger = logging.getLogger(__name__)

GDELT_URL = "https://api.gdeltproject.org/api/v2/doc/doc"
FINNHUB_NEWS_URL = "https://finnhub.io/api/v1/news"

# GDELT demande explicitement max 1 requête / 5s côté client public.
# On le respecte nous-mêmes en plus du cache Redis (cache.py) qui absorbe
# l'essentiel du trafic de nos propres utilisateurs.
# (Ne concerne que fetch_news_volume_history, toujours sur GDELT — le fil
# d'alertes visible est passé sur Finnhub, voir fetch_alerts.)
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

# L'API DOC 2.0 de GDELT ne couvre que les ~90 derniers jours de full-text ;
# au-delà, model.py complète le régresseur à 0 (pas de signal) plutôt que planter.
GDELT_HISTORY_MAX_DAYS = 90


def _build_query(devise: str) -> str:
    devise_terms = DEVISE_KEYWORDS.get(devise, [devise])
    devise_clause = " OR ".join(f'"{t}"' if " " in t else t for t in devise_terms)
    shock_clause = " OR ".join(f'"{t}"' if " " in t else t for t in SHOCK_KEYWORDS)
    return f"({devise_clause}) ({shock_clause})"


_TIMESPAN_RE = re.compile(r"^(\d+)([hdw])$")
_TIMESPAN_UNIT_SECONDS = {"h": 3600, "d": 86400, "w": 7 * 86400}


def _timespan_to_seconds(timespan: str, default_days: int = 2) -> int:
    m = _TIMESPAN_RE.match(timespan.strip().lower()) if timespan else None
    if not m:
        return default_days * 86400
    value, unit = m.groups()
    return int(value) * _TIMESPAN_UNIT_SECONDS[unit]


def fetch_alerts(devise: str, max_records: int = 5, timespan: str = "2d"):
    """Récupère les actus récentes (catégorie forex) via Finnhub et les filtre
    sur les mots-clés de la devise. Retourne None si Finnhub est indisponible/
    rate-limité ou si la clé API est absente (échec, à ne pas mettre en cache
    comme un vrai résultat) et [] s'il n'y a simplement aucune actu pertinente
    dans la fenêtre demandée (succès). Ne lève jamais d'exception."""
    if not config.FINNHUB_API_KEY:
        logger.warning("FINNHUB_API_KEY absente — alertes désactivées.")
        return None

    params = {"category": "forex", "token": config.FINNHUB_API_KEY}

    try:
        resp = requests.get(FINNHUB_NEWS_URL, params=params, timeout=config.FX_API_TIMEOUT)
        resp.raise_for_status()
        data = resp.json()
    except (requests.RequestException, ValueError) as e:
        logger.warning("Appel Finnhub échoué pour %s : %s — alertes désactivées.", devise, e)
        return None

    if not isinstance(data, list):
        logger.warning("Réponse Finnhub inattendue pour %s : %r", devise, data)
        return None

    keywords = [k.lower() for k in DEVISE_KEYWORDS.get(devise, [devise])]
    cutoff_ts = time.time() - _timespan_to_seconds(timespan)

    matches = []
    for a in data:
        headline = a.get("headline") or ""
        summary = a.get("summary") or ""
        url = a.get("url")
        published_at = a.get("datetime")
        if not headline or not url or not isinstance(published_at, (int, float)):
            continue
        if published_at < cutoff_ts:
            continue
        haystack = f"{headline} {summary}".lower()
        if not any(k in haystack for k in keywords):
            continue
        matches.append({
            "title": headline,
            "url": url,
            "source": a.get("source") or "",
            "seendate": datetime.fromtimestamp(published_at, tz=timezone.utc).strftime("%Y%m%dT%H%M%SZ"),
            "_datetime": published_at,
        })

    matches.sort(key=lambda m: m["_datetime"], reverse=True)
    for m in matches:
        del m["_datetime"]
    return matches[:max_records]


def fetch_news_volume_history(devise: str, start_date, end_date) -> pd.DataFrame:
    """Volume quotidien d'articles choc/devise via GDELT (mode timelinevol),
    utilisé comme régresseur macro dans model.py. Limité aux ~90 derniers
    jours (voir GDELT_HISTORY_MAX_DAYS) : model.py complète le reste à 0.
    Ne lève jamais d'exception : dégrade en DataFrame vide si GDELT est
    indisponible, rate-limite ou renvoie un format inattendu."""
    global _last_call_at

    window_start = max(start_date, end_date - pd.Timedelta(days=GDELT_HISTORY_MAX_DAYS))

    elapsed = time.monotonic() - _last_call_at
    if elapsed < _MIN_INTERVAL_SECONDS:
        time.sleep(_MIN_INTERVAL_SECONDS - elapsed)

    params = {
        "query": _build_query(devise),
        "mode": "timelinevol",
        "format": "json",
        "STARTDATETIME": window_start.strftime("%Y%m%d%H%M%S"),
        "ENDDATETIME": end_date.strftime("%Y%m%d%H%M%S"),
    }

    try:
        _last_call_at = time.monotonic()
        resp = requests.get(GDELT_URL, params=params, timeout=config.FX_API_TIMEOUT)
        resp.raise_for_status()
        points = resp.json()["timeline"][0]["data"]
    except (requests.RequestException, ValueError, KeyError, IndexError, TypeError) as e:
        logger.warning(
            "Appel GDELT (timelinevol) échoué pour %s : %s — news_volume désactivé.", devise, e,
        )
        return pd.DataFrame(columns=["date", "news_volume"])

    rows = []
    for p in points:
        try:
            rows.append({
                "date": pd.to_datetime(p["date"], format="%Y%m%d%H%M%S").normalize(),
                "news_volume": float(p["value"]),
            })
        except (KeyError, ValueError, TypeError):
            continue

    if not rows:
        return pd.DataFrame(columns=["date", "news_volume"])

    return pd.DataFrame(rows).groupby("date", as_index=False)["news_volume"].mean()
