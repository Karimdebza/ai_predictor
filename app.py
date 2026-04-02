from flask import Flask, jsonify, render_template
from model import train_model
import numpy as np

app = Flask(__name__)

# entraîner le modèle une seule fois
model, size = train_model()

@app.route("/gui")
def gui():
    return render_template("index.html")

@app.route("/")
def home():
    return "API Prediction OK"

@app.route("/predict")
def predict():
    next_day = np.array([[size + 1]])
    prediction = model.predict(next_day)
    return jsonify({
        "prediction_EUR_MAD": float(prediction[0])
    })

if __name__ == "__main__":
    app.run(debug=True)