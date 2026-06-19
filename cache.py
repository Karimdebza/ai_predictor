import logging
import os

import redis
import json

import config

logger = logging.getLogger(__name__)

REDIS_URL = os.getenv("REDIS_URL")
REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))

if REDIS_URL:
    r = redis.from_url(REDIS_URL, decode_responses=True)
else:
    r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)

try:
    r.ping()
    logger.info("Redis connecté : %s", REDIS_URL or f"{REDIS_HOST}:{REDIS_PORT}")
except Exception as e:
    logger.error("Redis non disponible : %s", e)


def is_redis_available():
    try:
        return r.ping()
    except Exception:
        return False


def get_cache(key: str):
    try:
        data = r.get(key)
        return json.loads(data) if data else None
    except Exception as e:
        logger.warning("Échec de lecture du cache pour %s : %s", key, e)
        return None


def set_cache(key: str, value: dict, ttl: int = config.RESULT_CACHE_TTL):
    try:
        r.setex(key, ttl, json.dumps(value))
    except Exception as e:
        logger.warning("Échec d'écriture du cache pour %s : %s", key, e)


def is_rate_limited(ip: str):
    key = f"rate:{ip}"

    try:
        current = r.incr(key)

        if current == 1:
            r.expire(key, config.RATE_LIMIT_WINDOW)

        if current > config.RATE_LIMIT:
            return True

        return False

    except Exception as e:
        logger.warning("Échec du rate limiting pour %s : %s", ip, e)
        return False
