from flask import Flask, jsonify, render_template, request
from model import train_model, predict_future

app = Flask(__name__)

DEVICES = ["MAD", "USD", "GBP", "JPY"]


@app.route("/")
def home():
    return render_template("index.html", devices=DEVICES)


@app.route("/predict")
def predict():
    to_currency = request.args.get("devise", "MAD")
    days = int(request.args.get("days", 5))

    model, df = train_model(to_currency)
    pred_dates, predictions, lower, upper = predict_future(model, df, days)

    return jsonify({
        "dates": df["date"].dt.strftime("%Y-%m-%d").tolist(),
        "historic": df["eur_to"].tolist(),
        "pred_dates": [d.strftime("%Y-%m-%d") for d in pred_dates],
        "predictions": predictions,
        "lower": lower,
        "upper": upper,
    })


if __name__ == "__main__":
    app.run(debug=True)