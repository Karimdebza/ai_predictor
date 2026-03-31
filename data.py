import requests

def get_data():
    url = "https://api.frankfurter.dev/v2/rate/EUR/MAD"
    response = requests.get(url)
    data = response.json()

    # sécurité
    if "rate" not in data:
        raise Exception(f"API n'a pas renvoyé 'rate': {data}")

    # retourne une liste pour LinearRegression
    return [data["rate"]]