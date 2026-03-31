from sklearn.linear_model import LinearRegression
import numpy as np
from data import get_data

def train_model():
    values = get_data()

    X = np.array(range(len(values))).reshape(-1, 1)
    y = np.array(values)

    model = LinearRegression()
    model.fit(X, y)

    return model, len(values)