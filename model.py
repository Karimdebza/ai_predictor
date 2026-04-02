import numpy as np
import pandas as pd
import requests
from sklearn.linear_model import LinearRegression

def get_historic_data(devise="MAD", days=30):
    # récupère les 30 derniers jours depuis l'API Frankfurter
    end = pd.Timestamp.today()
    start = end - pd.Timedelta(days=days)
    url = f"https://api.frankfurter.dev/v2/rate/EUR/{devise}?start_date={start.date()}&end_date={end.date()}"
    r = requests.get(url)
    data = r.json()

    # le retour dépend de l'API v2
    historic = list(data.get("rate", [10]*days))  # fallback si l'API change
    return historic

def train_model():
    # modèle simple linéaire
    size = 100
    X = np.arange(size).reshape(-1,1)
    y = np.linspace(10, 11, size)  # mock taux EUR->MAD
    model = LinearRegression().fit(X, y)
    return model, size