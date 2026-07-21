import time

import pandas as pd
from prophet import Prophet
from data import get_fix_history, get_oil_price_history
from news import fetch_news_volume_history
import numpy as np

import config

_model_cache = {}


def _add_features(df, oil_df, news_df):
    df = df.copy()
    df["ma7"] = df["eur_to"].rolling(7).mean()
    df["volatility7"] = df["eur_to"].rolling(7).std()

    if not oil_df.empty:
        df = df.merge(oil_df, on="date", how="left")
        # Le Brent ne cote pas les jours fériés US ; on prolonge la dernière valeur connue.
        df["oil_price"] = df["oil_price"].ffill().bfill()
    else:
        df["oil_price"] = 0.0
    df["oil_price"] = df["oil_price"].fillna(0.0)

    # GDELT ne couvre que les ~90 derniers jours : 0 (pas de signal) avant cette fenêtre.
    if not news_df.empty:
        df = df.merge(news_df, on="date", how="left")
    else:
        df["news_volume"] = 0.0
    df["news_volume"] = df["news_volume"].fillna(0.0)

    df = df.dropna().reset_index(drop=True)

    if df.empty:
        raise ValueError("Historique insuffisant pour calculer les indicateurs (ma7/volatility7)")

    return df


def _fit_prophet(prophet_df):
    model = Prophet(
        daily_seasonality=False,
        weekly_seasonality=True,
        yearly_seasonality=True,
        changepoint_prior_scale=0.05,
    )
    model.add_regressor("ma7")
    model.add_regressor("volatility7")
    model.add_regressor("oil_price")
    model.add_regressor("news_volume")
    model.fit(prophet_df)
    return model


def train_model(to_currency="MAD"):
    end_date = pd.Timestamp.today().normalize()
    start_date = end_date - pd.Timedelta(days=365)

    fx = get_fix_history(to_currency, start_date, end_date)
    oil = get_oil_price_history(start_date, end_date)
    news = fetch_news_volume_history(to_currency, start_date, end_date)
    df = _add_features(fx, oil, news)

    # Prophet attend ds + y
    prophet_df = df[["date", "eur_to", "ma7", "volatility7", "oil_price", "news_volume"]].rename(
        columns={"date": "ds", "eur_to": "y"}
    )

    model = _fit_prophet(prophet_df)

    return model, df


def get_or_train_model(to_currency="MAD"):
    """Modèle Prophet mis en cache mémoire par devise pour éviter de
    ré-entraîner à chaque requête (entraînement coûteux en CPU)."""
    cached = _model_cache.get(to_currency)
    if cached is not None:
        model, df, trained_at = cached
        if time.time() - trained_at < config.MODEL_CACHE_TTL:
            return model, df

    model, df = train_model(to_currency)
    _model_cache[to_currency] = (model, df, time.time())
    return model, df


def predict_future(model, df, days=5):
    last_date = df["date"].iloc[-1]
    future_rows = []

    for i in range(1, days + 1):
        # On projette ma7, volatility7, oil_price et news_volume avec les dernières valeurs connues
        future_rows.append({
            "ds": last_date + pd.Timedelta(days=i),
            "ma7": df["ma7"].iloc[-1],
            "volatility7": df["volatility7"].iloc[-1],
            "oil_price": df["oil_price"].iloc[-1],
            "news_volume": df["news_volume"].iloc[-1],
        })

    future_df = pd.DataFrame(future_rows)
    forecast = model.predict(future_df)

    pred_dates = forecast["ds"].tolist()
    predictions = forecast["yhat"].tolist()
    lower = forecast["yhat_lower"].tolist()
    upper = forecast["yhat_upper"].tolist()

    return pred_dates, predictions, lower, upper


def backtest(to_currency="MAD"):
    end_date = pd.Timestamp.today().normalize()
    start_date = end_date - pd.Timedelta(days=365)

    fx = get_fix_history(to_currency, start_date, end_date)
    oil = get_oil_price_history(start_date, end_date)
    news = fetch_news_volume_history(to_currency, start_date, end_date)
    df = _add_features(fx, oil, news)

    cut_off = len(df) - 7
    train_df = df.iloc[:cut_off].copy()
    test_df = df.iloc[cut_off:].copy()

    prophet_df = train_df[["date", "eur_to", "ma7", "volatility7", "oil_price", "news_volume"]].rename(
        columns={"date": "ds", "eur_to": "y"}
    )

    model = _fit_prophet(prophet_df)

    future_rows = []
    for i in range(1, len(test_df) + 1):
        future_rows.append({
            "ds": train_df["date"].iloc[-1] + pd.Timedelta(days=i),
            "ma7": train_df["ma7"].iloc[-1],
            "volatility7": train_df["volatility7"].iloc[-1],
            "oil_price": train_df["oil_price"].iloc[-1],
            "news_volume": train_df["news_volume"].iloc[-1],
        })

    future_df = pd.DataFrame(future_rows)
    forecast = model.predict(future_df)

    predicted = forecast["yhat"].values
    actual = test_df["eur_to"].values

    mae = float(np.mean(np.abs(predicted - actual)))
    mape = float(np.mean(np.abs((predicted - actual) / actual))) * 100
    details = []

    for i in range(len(test_df)):
        details.append({
            "date": test_df["date"].iloc[i].strftime("%Y-%m-%d"),
            "actual": round(float(actual[i]), 4),
            "predicted": round(float(predicted[i]), 4),
            "error": round(abs(float(predicted[i]) - float(actual[i])), 4),
        })

    return {
        "mae": round(mae, 4),
        "mape": round(mape, 2),
        "details": details
    }
