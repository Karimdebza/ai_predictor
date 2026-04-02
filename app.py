from flask import Flask, jsonify, render_template, request
from model import train_model, get_historic_data
import numpy as np
from datetime import datetime, timedelta

app = Flask(__name__)

model, size = train_model()

@app.route("/gui")
def gui():
    return render_template("index.html")

@app.route("/")
def home():
    return "API Prediction OK"

@app.route("/predict")
def predict():
    devise = request.args.get('devise', 'MAD')
    days = int(request.args.get('days', 5))

    historic = get_historic_data(devise) 
    last_day = size

    pred_dates = []
    predictions = []

    for i in range(1, days+1):
        next_day = np.array([[last_day + i]])
        pred = model.predict(next_day)
        predictions.append(float(pred[0]))
        pred_dates.append((datetime.today() + timedelta(days=i)).strftime("%Y-%m-%d"))

    dates = [(datetime.today() - timedelta(days=i)).strftime("%Y-%m-%d") for i in range(len(historic))]

    return jsonify({
        "historic": historic,
        "predictions": predictions,
        "dates": dates,
        "pred_dates": pred_dates
    })

if __name__ == "__main__":
    app.run(debug=True)