from flask import Flask, jsonify, render_template, request
from flask_cors import CORS
from model import train_model, predict_future, backtest
from cache import get_cache, is_rate_limited, set_cache
import logging
logger = logging.getLogger(__name__)
app = Flask(__name__)
# CORS(app, origins=["https://fx-dashboard-9yq303706-karimdebzas-projects.vercel.app/"])
CORS(app)

DEVICES = ["MAD", "USD", "GBP", "JPY"]


@app.route("/")
def home():
    return render_template("index.html", devices=DEVICES)

@app.route("/health")
def health():
    return jsonify({"status": "ok"})

@app.route("/predict")
def predict():
    ip = request.headers.get("X-Forwarded-For", request.remote_addr)

    if is_rate_limited(ip):
        return jsonify({"error": "Too many requests"}), 429
    to_currency = request.args.get("devise", "MAD").upper()
    days = int(request.args.get("days", 5))

    if to_currency not in DEVICES:
        return jsonify({"error": "Devise non supportée"}), 400

    try:
        cache_key = f"predict:{to_currency}:{days}"
        cached = get_cache(cache_key)

        if cached:
             logger.info("Cache HIT pour %s", cache_key)
             return jsonify(cached)
        else:
            logger.info("Cache MISS pour %s", cache_key)
            model, df = train_model(to_currency)
            # On stocke pas le modèle Prophet dans Redis
            # On recalcule si pas en mémoire
            pass

        pred_dates, predictions, lower, upper = predict_future(model, df, days)

        result = {
            "dates": df["date"].dt.strftime("%Y-%m-%d").tolist(),
            "historic": df["eur_to"].tolist(),
            "pred_dates": [d.strftime("%Y-%m-%d") for d in pred_dates],
            "predictions": predictions,
            "lower": lower,
            "upper": upper,
        }

        set_cache(f"predict:{to_currency}:{days}", result, ttl=3600)
        return jsonify(result)

    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/backtest")
def run_backtest():
    ip = request.headers.get("X-Forwarded-For", request.remote_addr)

    if is_rate_limited(ip):
        return jsonify({"error": "Too many requests"}), 429  
    to_currency = request.args.get("devise", "MAD").upper()

    if to_currency not in DEVICES:
        return jsonify({"error": "Devise non supportée"}), 400

    try:
        cache_key = f"backtest:{to_currency}"
        cached = get_cache(cache_key)

        if cached:
            return jsonify(cached)

        result = backtest(to_currency)
        set_cache(cache_key, result, ttl=3600)
        return jsonify(result)

    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/compare")
def compare():
    ip = request.headers.get("X-Forwarded-For", request.remote_addr)
    if is_rate_limited(ip):
        return jsonify({"error": "Too many requests"}), 429
    days = int(request.args.get("days", 5))
    results = {}

    for dev in DEVICES:
        try:
            cache_key = f"predict:{dev}:{days}"
            cached = get_cache(cache_key)

            if cached:
                results[dev] = cached
            else:
                model, df = train_model(dev)
                pred_dates, predictions, lower, upper = predict_future(model, df, days)
                data = {
                    "dates": df["date"].dt.strftime("%Y-%m-%d").tolist(),
                    "historic": df["eur_to"].tolist(),
                    "pred_dates": [d.strftime("%Y-%m-%d") for d in pred_dates],
                    "predictions": predictions,
                    "lower": lower,
                    "upper": upper,
                }
                set_cache(cache_key, data, ttl=3600)
                results[dev] = data

        except Exception as e:
            results[dev] = {"error": str(e)}
    return jsonify(results)


if __name__ == "__main__":
    app.run(debug=True)