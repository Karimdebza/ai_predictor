import pytest
from unittest.mock import patch, MagicMock
from datetime import date
import pandas as pd
from app import app


# ─── Fixtures ────────────────────────────────────────────────────────────────

@pytest.fixture
def client():
    app.config["TESTING"] = True
    # Vide le cache entre chaque test pour éviter les effets de bord
    with patch.dict("app._cache", {}, clear=True), \
         patch.dict("app._backtest_cache", {}, clear=True):
        with app.test_client() as client:
            yield client


# ─── Données mock ─────────────────────────────────────────────────────────────

def make_mock_df():
    """DataFrame minimal qui imite ce que train_model retourne."""
    return pd.DataFrame({
        "date": pd.to_datetime(["2025-01-01", "2025-01-02", "2025-01-03"]),
        "eur_to": [1.05, 1.06, 1.07],
    })

MOCK_PRED_DATES  = [date(2025, 1, 4), date(2025, 1, 5)]
MOCK_PREDICTIONS = [1.08, 1.09]
MOCK_LOWER       = [1.07, 1.08]
MOCK_UPPER       = [1.09, 1.10]

MOCK_BACKTEST_RESULT = {
    "mae": 0.0021,
    "mape": 0.19,
    "details": [
        {"date": "2025-03-28", "actual": 1.0812, "predicted": 1.0834, "error": 0.0022},
        {"date": "2025-03-29", "actual": 1.0798, "predicted": 1.0819, "error": 0.0021},
    ],
}


# ─── /health ─────────────────────────────────────────────────────────────────

class TestHealth:

    def test_health_returns_200(self, client):
        assert client.get("/health").status_code == 200

    def test_health_returns_ok_status(self, client):
        data = client.get("/health").get_json()
        assert data.get("status") == "ok"


# ─── /predict ────────────────────────────────────────────────────────────────

class TestPredict:

    def test_predict_returns_200(self, client):
        with patch("app.train_model", return_value=(MagicMock(), make_mock_df())), \
             patch("app.predict_future", return_value=(MOCK_PRED_DATES, MOCK_PREDICTIONS, MOCK_LOWER, MOCK_UPPER)):
            assert client.get("/predict?devise=USD&days=5").status_code == 200

    def test_predict_response_keys(self, client):
        with patch("app.train_model", return_value=(MagicMock(), make_mock_df())), \
             patch("app.predict_future", return_value=(MOCK_PRED_DATES, MOCK_PREDICTIONS, MOCK_LOWER, MOCK_UPPER)):
            data = client.get("/predict?devise=USD&days=5").get_json()
        for key in ("dates", "historic", "pred_dates", "predictions", "lower", "upper"):
            assert key in data, f"Clé manquante : {key}"

    def test_predict_pred_dates_formatted(self, client):
        with patch("app.train_model", return_value=(MagicMock(), make_mock_df())), \
             patch("app.predict_future", return_value=(MOCK_PRED_DATES, MOCK_PREDICTIONS, MOCK_LOWER, MOCK_UPPER)):
            data = client.get("/predict?devise=USD&days=2").get_json()
        assert data["pred_dates"] == ["2025-01-04", "2025-01-05"]

    def test_predict_lower_upper_same_length(self, client):
        with patch("app.train_model", return_value=(MagicMock(), make_mock_df())), \
             patch("app.predict_future", return_value=(MOCK_PRED_DATES, MOCK_PREDICTIONS, MOCK_LOWER, MOCK_UPPER)):
            data = client.get("/predict?devise=USD&days=5").get_json()
        assert len(data["lower"]) == len(data["upper"])

    def test_predict_all_devises(self, client):
        with patch("app.train_model", return_value=(MagicMock(), make_mock_df())), \
             patch("app.predict_future", return_value=(MOCK_PRED_DATES, MOCK_PREDICTIONS, MOCK_LOWER, MOCK_UPPER)):
            for devise in ("MAD", "USD", "GBP", "JPY"):
                resp = client.get(f"/predict?devise={devise}&days=5")
                assert resp.status_code == 200, f"Échec pour la devise {devise}"

    def test_predict_missing_devise_uses_default_mad(self, client):
        """Sans paramètre devise, MAD est la valeur par défaut → doit passer."""
        with patch("app.train_model", return_value=(MagicMock(), make_mock_df())), \
             patch("app.predict_future", return_value=(MOCK_PRED_DATES, MOCK_PREDICTIONS, MOCK_LOWER, MOCK_UPPER)):
            assert client.get("/predict?days=5").status_code == 200

    def test_predict_unsupported_devise_returns_400(self, client):
        response = client.get("/predict?devise=XYZ&days=5")
        assert response.status_code == 400
        assert "error" in response.get_json()

    def test_predict_train_model_error_returns_500(self, client):
        with patch("app.train_model", side_effect=Exception("Frankfurter timeout")):
            response = client.get("/predict?devise=USD&days=5")
        assert response.status_code == 500
        assert "error" in response.get_json()

    def test_predict_predict_future_error_returns_500(self, client):
        with patch("app.train_model", return_value=(MagicMock(), make_mock_df())), \
             patch("app.predict_future", side_effect=Exception("Prophet error")):
            response = client.get("/predict?devise=USD&days=5")
        assert response.status_code == 500

    def test_predict_cache_hit_does_not_retrain(self, client):
        """Deux appels pour la même devise → train_model appelé une seule fois."""
        with patch("app.train_model", return_value=(MagicMock(), make_mock_df())) as mock_train, \
             patch("app.predict_future", return_value=(MOCK_PRED_DATES, MOCK_PREDICTIONS, MOCK_LOWER, MOCK_UPPER)):
            client.get("/predict?devise=USD&days=5")
            client.get("/predict?devise=USD&days=3")
            assert mock_train.call_count == 1


# ─── /backtest ───────────────────────────────────────────────────────────────

class TestBacktest:

    def test_backtest_returns_200(self, client):
        with patch("app.backtest", return_value=MOCK_BACKTEST_RESULT):
            assert client.get("/backtest?devise=USD").status_code == 200

    def test_backtest_response_keys(self, client):
        with patch("app.backtest", return_value=MOCK_BACKTEST_RESULT):
            data = client.get("/backtest?devise=USD").get_json()
        assert "mae" in data and "mape" in data and "details" in data

    def test_backtest_mape_is_number(self, client):
        with patch("app.backtest", return_value=MOCK_BACKTEST_RESULT):
            data = client.get("/backtest?devise=USD").get_json()
        assert isinstance(data["mape"], (int, float))

    def test_backtest_details_structure(self, client):
        with patch("app.backtest", return_value=MOCK_BACKTEST_RESULT):
            data = client.get("/backtest?devise=USD").get_json()
        for row in data["details"]:
            for key in ("date", "actual", "predicted", "error"):
                assert key in row, f"Clé manquante dans details : {key}"

    def test_backtest_all_devises(self, client):
        with patch("app.backtest", return_value=MOCK_BACKTEST_RESULT):
            for devise in ("MAD", "USD", "GBP", "JPY"):
                resp = client.get(f"/backtest?devise={devise}")
                assert resp.status_code == 200

    def test_backtest_missing_devise_uses_default_mad(self, client):
        with patch("app.backtest", return_value=MOCK_BACKTEST_RESULT):
            assert client.get("/backtest").status_code == 200

    def test_backtest_unsupported_devise_returns_400(self, client):
        response = client.get("/backtest?devise=XYZ")
        assert response.status_code == 400

    def test_backtest_error_returns_500(self, client):
        with patch("app.backtest", side_effect=Exception("Model not cached")):
            response = client.get("/backtest?devise=USD")
        assert response.status_code == 500
        assert "error" in response.get_json()

    def test_backtest_cache_hit_does_not_rerun(self, client):
        """Deuxième appel → backtest() ne tourne qu'une seule fois."""
        with patch("app.backtest", return_value=MOCK_BACKTEST_RESULT) as mock_bt:
            client.get("/backtest?devise=USD")
            client.get("/backtest?devise=USD")
            assert mock_bt.call_count == 1


# ─── CORS ────────────────────────────────────────────────────────────────────

# class TestCORS:

#     def test_cors_header_on_predict(self, client):
#         with patch("app.train_model", return_value=(MagicMock(), make_mock_df())), \
#              patch("app.predict_future", return_value=(MOCK_PRED_DATES, MOCK_PREDICTIONS, MOCK_LOWER, MOCK_UPPER)):
#             response = client.get(
#                 "/predict?devise=USD&days=5",
#                 headers={"Origin": "https://fx-dashboard.vercel.app"},
#             )
#         assert "Access-Control-Allow-Origin" in response.headers

#     def test_cors_header_on_backtest(self, client):
#         with patch("app.backtest", return_value=MOCK_BACKTEST_RESULT):
#             response = client.get(
#                 "/backtest?devise=USD",
#                 headers={"Origin": "https://fx-dashboard.vercel.app"},
#             )
#         assert "Access-Control-Allow-Origin" in response.headers