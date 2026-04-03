from flask import Flask, jsonify, render_template, request
from flask_cors import CORS
from model import train_model, predict_future, backtest

app = Flask(__name__)
# CORS(app, origins=["https://fx-dashboard-9yq303706-karimdebzas-projects.vercel.app/"])
CORS(app)

DEVICES = ["MAD", "USD", "GBP", "JPY"]
_cache = {}
_backtest_cache = {}

@app.route("/")
def home():
    return render_template("index.html", devices=DEVICES)

@app.route("/health")
def health():
    return jsonify({"status": "ok"})

@app.route("/predict")
def predict():
    to_currency = request.args.get("devise", "MAD").upper()
    days = int(request.args.get("days", 5))

    if to_currency not in DEVICES:
        return jsonify({"error": "Devise non supportée"}), 400

    try:
        if to_currency not in _cache:
            _cache[to_currency] = train_model(to_currency)
        model, df = _cache[to_currency]

        pred_dates, predictions, lower, upper = predict_future(model, df, days)

        return jsonify({
            "dates": df["date"].dt.strftime("%Y-%m-%d").tolist(),
            "historic": df["eur_to"].tolist(),
            "pred_dates": [d.strftime("%Y-%m-%d") for d in pred_dates],
            "predictions": predictions,
            "lower": lower,
            "upper": upper,
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/backtest")
def run_backtest():
    to_currency = request.args.get("devise", "MAD").upper()
    
    if to_currency not in DEVICES:
        return jsonify({"error": "Devise non supportée"}), 400
    
    try:
        if to_currency not in _backtest_cache:
            _backtest_cache[to_currency] = backtest(to_currency)
        return jsonify(_backtest_cache[to_currency])
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run(debug=True)