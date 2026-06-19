import os

DEBUG = os.getenv("FLASK_DEBUG", "false").lower() == "true"
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()

DEFAULT_CORS_ORIGINS = "https://fx-dashboard-beta.vercel.app,http://localhost:4200"

CORS_ORIGINS = [
    origin.strip()
    for origin in os.getenv("CORS_ORIGINS", DEFAULT_CORS_ORIGINS).split(",")
    if origin.strip()
]

RATE_LIMIT = int(os.getenv("RATE_LIMIT", 60))
RATE_LIMIT_WINDOW = int(os.getenv("RATE_LIMIT_WINDOW", 60))

RESULT_CACHE_TTL = int(os.getenv("RESULT_CACHE_TTL", 3600))
MODEL_CACHE_TTL = int(os.getenv("MODEL_CACHE_TTL", 3600))

MIN_DAYS = int(os.getenv("MIN_DAYS", 1))
MAX_DAYS = int(os.getenv("MAX_DAYS", 30))

FX_API_TIMEOUT = int(os.getenv("FX_API_TIMEOUT", 10))
