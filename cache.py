import json
import logging
import os
import time
from collections import defaultdict

import redis

import config

logger = logging.getLogger(__name__)

# ─── Connexion Redis ──────────────────────────────────
REDIS_URL = os.getenv("REDIS_URL")
REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))

if REDIS_URL:
    _r = redis.from_url(REDIS_URL, decode_responses=True)
else:
    _r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True, socket_connect_timeout=1)

_redis_ok: bool = False
try:
    _r.ping()
    _redis_ok = True
    logger.info("Redis connecté : %s", REDIS_URL or f"{REDIS_HOST}:{REDIS_PORT}")
except Exception as e:
    logger.warning("Redis non disponible (%s) — fallback cache mémoire activé.", e)

# ─── Fallback mémoire ────────────────────────────────
# { key: (valeur, expiry_timestamp) }
_mem: dict[str, tuple[object, float]] = {}

# Rate limiter mémoire : { ip: [timestamp, ...] }
_rate_mem: dict[str, list[float]] = defaultdict(list)


def _mem_get(key: str):
    entry = _mem.get(key)
    if entry is None:
        return None
    value, expiry = entry
    if time.time() > expiry:
        del _mem[key]
        return None
    return value


def _mem_set(key: str, value: object, ttl: int):
    _mem[key] = (value, time.time() + ttl)

    # Nettoyage léger : purge les entrées expirées si le dict grossit
    if len(_mem) > 500:
        now = time.time()
        expired = [k for k, (_, exp) in _mem.items() if now > exp]
        for k in expired:
            del _mem[k]


# ─── API publique ─────────────────────────────────────
def is_redis_available() -> bool:
    try:
        return bool(_r.ping())
    except Exception:
        return False


def get_cache(key: str):
    if _redis_ok:
        try:
            data = _r.get(key)
            return json.loads(data) if data else None
        except Exception:
            pass
    return _mem_get(key)


def set_cache(key: str, value: dict, ttl: int = config.RESULT_CACHE_TTL):
    if _redis_ok:
        try:
            _r.setex(key, ttl, json.dumps(value))
            return
        except Exception:
            pass
    _mem_set(key, value, ttl)


def is_rate_limited(ip: str) -> bool:
    if _redis_ok:
        key = f"rate:{ip}"
        try:
            current = _r.incr(key)
            if current == 1:
                _r.expire(key, config.RATE_LIMIT_WINDOW)
            return current > config.RATE_LIMIT
        except Exception:
            pass

    # Fallback : fenêtre glissante en mémoire
    now = time.time()
    window_start = now - config.RATE_LIMIT_WINDOW
    timestamps = _rate_mem[ip]
    _rate_mem[ip] = [t for t in timestamps if t > window_start]
    _rate_mem[ip].append(now)
    return len(_rate_mem[ip]) > config.RATE_LIMIT
