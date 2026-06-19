import time

import pandas as pd
from prophet import Prophet
from data import get_fix_history
import numpy as np

import config

_model_cache = {}


def _add_features(df):
    df = df.copy()
    df["ma7"] = df["eur_to"].rolling(7).mean()
    df["volatility7"] = df["eur_to"].rolling(7).std()
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
    model.fit(prophet_df)
    return model


def train_model(to_currency="MAD"):
    end_date = pd.Timestamp.today().normalize()
    start_date = end_date - pd.Timedelta(days=365)

    fx = get_fix_history(to_currency, start_date, end_date)
    df = _add_features(fx)

    # Prophet attend ds + y
    prophet_df = df[["date", "eur_to", "ma7", "volatility7"]].rename(
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
        # On projette ma7 et volatility7 avec les dernières valeurs connues
        future_rows.append({
            "ds": last_date + pd.Timedelta(days=i),
            "ma7": df["ma7"].iloc[-1],
            "volatility7": df["volatility7"].iloc[-1],
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
    df = _add_features(fx)

    cut_off = len(df) - 7
    train_df = df.iloc[:cut_off].copy()
    test_df = df.iloc[cut_off:].copy()

    prophet_df = train_df[["date", "eur_to", "ma7", "volatility7"]].rename(
        columns={"date": "ds", "eur_to": "y"}
    )

    model = _fit_prophet(prophet_df)

    future_rows = []
    for i in range(1, len(test_df) + 1):
        future_rows.append({
            "ds": train_df["date"].iloc[-1] + pd.Timedelta(days=i),
            "ma7": train_df["ma7"].iloc[-1],
            "volatility7": train_df["volatility7"].iloc[-1],
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
            "actual": round(actual[i], 4),
            "predicted": round(float(predicted[i]), 4),
            "error": round(abs(predicted[i] - actual[i]), 4),
        })

    return {
        "mae": round(mae, 4),
        "mape": round(mape, 2),
        "details": details
    }
