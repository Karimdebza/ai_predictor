# ai_predictor

Predire la devise DU MAD USD et dautre le but et davoir une verité proche plus c'est proche plus cest fiable

## Variables d'environnement

| Variable | Défaut | Description |
|---|---|---|
| `REDIS_URL` | — | URL de connexion Redis (prioritaire sur `REDIS_HOST`/`REDIS_PORT`) |
| `REDIS_HOST` | `localhost` | Hôte Redis si `REDIS_URL` n'est pas défini |
| `REDIS_PORT` | `6379` | Port Redis si `REDIS_URL` n'est pas défini |
| `FLASK_DEBUG` | `false` | Active le mode debug Flask (jamais `true` en prod) |
| `LOG_LEVEL` | `INFO` | Niveau de logging (`DEBUG`, `INFO`, `WARNING`, ...) |
| `CORS_ORIGINS` | `https://fx-dashboard-beta.vercel.app` | Origines autorisées (séparées par des virgules) |
| `RATE_LIMIT` | `60` | Requêtes max par IP sur la fenêtre `RATE_LIMIT_WINDOW` |
| `RATE_LIMIT_WINDOW` | `60` | Fenêtre du rate limit, en secondes |
| `RESULT_CACHE_TTL` | `3600` | Durée de vie du cache Redis des résultats, en secondes |
| `MODEL_CACHE_TTL` | `3600` | Durée de vie du cache mémoire du modèle Prophet entraîné, en secondes |
| `MIN_DAYS` / `MAX_DAYS` | `1` / `30` | Bornes acceptées pour le paramètre `days` |
| `FX_API_TIMEOUT` | `10` | Timeout (s) des appels à l'API Frankfurter |

## Endpoints

- `GET /` — page de démo (template local, non utilisé en prod ; le dashboard réel est sur Vercel)
- `GET /health` — statut de l'app et de la connexion Redis
- `GET /predict?devise=USD&days=5` — prédiction Prophet pour une devise
- `GET /backtest?devise=USD` — backtest sur les 7 derniers jours
- `GET /compare?days=5` — prédiction pour toutes les devises supportées (`MAD`, `USD`, `GBP`, `JPY`)
