
# FX Predictor — Exchange Rate Forecasting with ML

> Predicts EUR → MAD, USD, GBP, JPY exchange rates using a time-series ML model trained on 365 days of ECB data.

**[Live Demo →](https://ai-predictor-sskw.onrender.com)**

---

## Overview

FX Predictor is a Python/Flask API that fetches historical exchange rate data from the ECB (European Central Bank), trains a [Prophet](https://facebook.github.io/prophet/) forecasting model per currency pair, and returns a 1–30 day prediction window with confidence intervals.

The frontend dashboard (separate repo: [fx-dashboard](https://github.com/Karimdebza/fx-dashboard)) consumes this API and visualizes forecasts with Chart.js.

---

## Architecture

```
ECB API (365 days of rates)
        ↓
   data.py — fetch & normalize
        ↓
   model.py — Prophet training + MAE scoring
        ↓
   app.py — Flask REST API
        ↓
fx-dashboard (Angular + Chart.js on Vercel)
```

---

## How it works

1. **Data ingestion** — `data.py` fetches the last 365 days of EUR → target currency rates from the ECB public API
2. **Training** — `model.py` trains a Prophet model on the historical data, computes the MAE (Mean Absolute Error) score as a reliability indicator
3. **Prediction** — the model outputs daily forecasts for the next N days (default: 5), with lower/upper confidence bounds
4. **Caching** — models are cached per currency to avoid re-training on every request

---

## API

```
GET /predict?devise=MAD&days=5
GET /backtest?devise=MAD
GET /compare?days=5
GET /health
```

**Response `/predict`:**
```json
{
  "dates": ["2025-01-01", "..."],
  "historic": [10.82, "..."],
  "pred_dates": ["2025-04-01", "..."],
  "predictions": [10.91, "..."],
  "lower": [10.85, "..."],
  "upper": [10.97, "..."]
}
```

**Supported currencies:** `MAD` · `USD` · `GBP` · `JPY`

---

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `REDIS_URL` | — | Redis connection URL (overrides `REDIS_HOST`/`REDIS_PORT`) |
| `REDIS_HOST` | `localhost` | Redis host if `REDIS_URL` is not set |
| `REDIS_PORT` | `6379` | Redis port if `REDIS_URL` is not set |
| `FLASK_DEBUG` | `false` | Enable Flask debug mode (never `true` in prod) |
| `LOG_LEVEL` | `INFO` | Logging level (`DEBUG`, `INFO`, `WARNING`, ...) |
| `CORS_ORIGINS` | `https://fx-dashboard-beta.vercel.app` | Allowed origins (comma-separated) |
| `RATE_LIMIT` | `60` | Max requests per IP in `RATE_LIMIT_WINDOW` |
| `RATE_LIMIT_WINDOW` | `60` | Rate limit window in seconds |
| `RESULT_CACHE_TTL` | `3600` | Redis result cache TTL in seconds |
| `MODEL_CACHE_TTL` | `3600` | In-memory Prophet model cache TTL in seconds |
| `MIN_DAYS` / `MAX_DAYS` | `1` / `30` | Accepted bounds for the `days` parameter |
| `FX_API_TIMEOUT` | `10` | Timeout (s) for Frankfurter API calls |

---

## Tech Stack

| Layer | Technology |
|---|---|
| Language | Python 3.11 |
| Framework | Flask |
| ML Model | Prophet (Meta) |
| Data Source | ECB Exchange Rate API |
| Evaluation | MAE (Mean Absolute Error) |
| Caching | Redis + in-memory fallback |
| Deployment | Render |

---

## Local setup

```bash
git clone https://github.com/Karimdebza/ai_predictor.git
cd ai_predictor
pip install -r requirements.txt
python app.py
```

API available at `http://localhost:5000`

---

## Related

- **Frontend:** [fx-dashboard](https://github.com/Karimdebza/fx-dashboard) — Angular 17 + Chart.js dashboard
- **Live:** [fx-dashboard-beta.vercel.app](https://fx-dashboard-beta.vercel.app)
