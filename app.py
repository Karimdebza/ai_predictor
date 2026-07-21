import logging
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed

import config

logging.basicConfig(level=config.LOG_LEVEL, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)

from flask import Flask, jsonify, render_template, request
from flask_cors import CORS

from model import get_or_train_model, predict_future, backtest
from cache import get_cache, is_rate_limited, is_redis_available, set_cache
from news import fetch_alerts

ALERTS_CACHE_TTL = 900  # 15 min : les news bougent plus vite que les prédictions FX

app = Flask(__name__)
CORS(app, origins=config.CORS_ORIGINS)

DEVICES = ["MAD", "USD", "GBP", "JPY", "VND"]


def _client_ip():
    return request.headers.get("X-Forwarded-For", request.remote_addr)


def _parse_days():
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


def _prewarm():
    """Entraîne les modèles + backtest en parallèle au démarrage.
    Avec gunicorn --workers 1 --threads N, le cache mémoire est partagé
    entre tous les threads → chaque utilisateur bénéficie du pre-warm."""
    logger.info("Pre-warm : démarrage (%d devises)", len(DEVICES))

    def _warm_predict(dev):
        try:
            model, df = get_or_train_model(dev)
            # Pré-calcule et met en cache le résultat pour les jours par défaut
            for days in (5, 7):
                key = f"predict:{dev}:{days}"
                if not get_cache(key):
                    set_cache(key, _build_prediction(dev, days))
            logger.info("Pre-warm predict OK : %s", dev)
        except Exception:
            logger.warning("Pre-warm predict échoué pour %s", dev, exc_info=True)

    def _warm_backtest(dev):
        try:
            key = f"backtest:{dev}"
            if not get_cache(key):
                result = backtest(dev)
                set_cache(key, result)
            logger.info("Pre-warm backtest OK : %s", dev)
        except Exception:
            logger.warning("Pre-warm backtest échoué pour %s", dev, exc_info=True)

    # Predict + backtest pour toutes les devises en parallèle (8 tâches)
    tasks = [(dev, kind) for dev in DEVICES for kind in ("predict", "backtest")]

    def _run(task):
        dev, kind = task
        if kind == "predict":
            _warm_predict(dev)
        else:
            _warm_backtest(dev)

    with ThreadPoolExecutor(max_workers=8) as ex:
        list(ex.map(_run, tasks))

    logger.info("Pre-warm terminé — predict + backtest prêts pour toutes les devises")


# Lancement en arrière-plan dès le démarrage (ne bloque pas Flask)
threading.Thread(target=_prewarm, daemon=True).start()


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
        logger.info("Cache HIT %s", cache_key)
        return jsonify(cached)

    logger.info("Cache MISS %s", cache_key)
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

    # Vérifier d'abord le cache pour chaque devise
    results = {}
    to_compute = []

    for dev in DEVICES:
        cache_key = f"predict:{dev}:{days}"
        cached = get_cache(cache_key)
        if cached:
            logger.info("Cache HIT compare:%s:%s", dev, days)
            results[dev] = cached
        else:
            to_compute.append(dev)

    if not to_compute:
        return jsonify(results)

    # Entraîner les devises manquantes en parallèle
    logger.info("Compare : %d devise(s) à calculer en parallèle : %s", len(to_compute), to_compute)

    def _compute(dev):
        data = _build_prediction(dev, days)
        set_cache(f"predict:{dev}:{days}", data)
        return dev, data

    with ThreadPoolExecutor(max_workers=len(to_compute)) as ex:
        futures = {ex.submit(_compute, dev): dev for dev in to_compute}
        for future in as_completed(futures):
            dev = futures[future]
            try:
                _, data = future.result()
                results[dev] = data
            except Exception:
                logger.exception("Échec prédiction parallèle pour %s", dev)
                results[dev] = {"error": "Prédiction indisponible pour cette devise"}

    return jsonify(results)


@app.route("/alerts")
def alerts():
    if is_rate_limited(_client_ip()):
        return jsonify({"error": "Too many requests"}), 429

    to_currency = request.args.get("devise", "MAD").upper()
    if to_currency not in DEVICES:
        return jsonify({"error": "Devise non supportée"}), 400

    cache_key = f"alerts:{to_currency}"
    cached = get_cache(cache_key)
    if cached is not None:
        return jsonify(cached)

    alerts_list = fetch_alerts(to_currency)
    if alerts_list is None:
        # Échec GDELT (rate-limit, timeout...) : ne pas mettre en cache, pour
        # ne pas verrouiller "aucune news" pendant 15 min sur un simple accident.
        return jsonify({"alerts": []})

    result = {"alerts": alerts_list}
    set_cache(cache_key, result, ttl=ALERTS_CACHE_TTL)
    return jsonify(result)


if __name__ == "__main__":
    app.run(debug=config.DEBUG)
