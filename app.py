import logging

import config

logging.basicConfig(level=config.LOG_LEVEL, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)

from flask import Flask, jsonify, render_template, request
from flask_cors import CORS

from model import get_or_train_model, predict_future, backtest
from cache import get_cache, is_rate_limited, is_redis_available, set_cache

app = Flask(__name__)
CORS(app, origins=config.CORS_ORIGINS)

DEVICES = ["MAD", "USD", "GBP", "JPY"]


def _client_ip():
    return request.headers.get("X-Forwarded-For", request.remote_addr)


def _parse_days():
    """Renvoie (days, erreur). erreur est None si la valeur est valide."""
    raw = request.args.get("days", "5")
    try:
        days = int(raw)
    except ValueError:
        return None, ("Paramètre 'days' invalide", 400)

    if not (config.MIN_DAYS <= days <= config.MAX_DAYS):
        return None, (f"'days' doit être entre {config.MIN_DAYS} et {config.MAX_DAYS}", 400)

    return days, None


def _build_prediction(to_currency, days):
    model, df = get_or_train_model(to_currency)
    pred_dates, predictions, lower, upper = predict_future(model, df, days)

    return {
        "dates": df["date"].dt.strftime("%Y-%m-%d").tolist(),
        "historic": df["eur_to"].tolist(),
        "pred_dates": [d.strftime("%Y-%m-%d") for d in pred_dates],
        "predictions": predictions,
        "lower": lower,
        "upper": upper,
    }


@app.errorhandler(Exception)
def handle_unexpected_error(e):
    logger.exception("Erreur interne inattendue")
    return jsonify({"error": "Erreur interne, réessayez plus tard"}), 500


@app.route("/")
def home():
    return render_template("index.html", devices=DEVICES)


@app.route("/health")
def health():
    return jsonify({"status": "ok", "redis": "ok" if is_redis_available() else "down"})


@app.route("/predict")
def predict():
    if is_rate_limited(_client_ip()):
        return jsonify({"error": "Too many requests"}), 429

    to_currency = request.args.get("devise", "MAD").upper()
    if to_currency not in DEVICES:
        return jsonify({"error": "Devise non supportée"}), 400

    days, error = _parse_days()
    if error:
        message, status = error
        return jsonify({"error": message}), status

    cache_key = f"predict:{to_currency}:{days}"
    cached = get_cache(cache_key)
    if cached:
        logger.info("Cache HIT pour %s", cache_key)
        return jsonify(cached)

    logger.info("Cache MISS pour %s", cache_key)
    result = _build_prediction(to_currency, days)
    set_cache(cache_key, result)
    return jsonify(result)


@app.route("/backtest")
def run_backtest():
    if is_rate_limited(_client_ip()):
        return jsonify({"error": "Too many requests"}), 429

    to_currency = request.args.get("devise", "MAD").upper()
    if to_currency not in DEVICES:
        return jsonify({"error": "Devise non supportée"}), 400

    cache_key = f"backtest:{to_currency}"
    cached = get_cache(cache_key)
    if cached:
        return jsonify(cached)

    result = backtest(to_currency)
    set_cache(cache_key, result)
    return jsonify(result)


@app.route("/compare")
def compare():
    if is_rate_limited(_client_ip()):
        return jsonify({"error": "Too many requests"}), 429

    days, error = _parse_days()
    if error:
        message, status = error
        return jsonify({"error": message}), status

    results = {}
    for dev in DEVICES:
        try:
            cache_key = f"predict:{dev}:{days}"
            cached = get_cache(cache_key)

            if cached:
                results[dev] = cached
            else:
                data = _build_prediction(dev, days)
                set_cache(cache_key, data)
                results[dev] = data
        except Exception as e:
            logger.exception("Échec de prédiction pour %s", dev)
            results[dev] = {"error": "Prédiction indisponible pour cette devise"}

    return jsonify(results)


if __name__ == "__main__":
    app.run(debug=config.DEBUG)
