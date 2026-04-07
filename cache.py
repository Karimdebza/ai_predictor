import redis
import json
import os 

r = redis.Redis(host=os.getenv("REDIS_HOST", "localhost"),
                port=int(os.getenv("REDIS_PORT", 6379)),
                decode_responses=True)

def get_cache(key:str):
    try:
        data = r.get(key)
        return json.loads(data) if data else None
    except Exception as e:
        return None
    
def set_cache(key:str, value:dict, ttl: int =3600):
    try:
        r.setex(key, ttl, json.dumps(value))
    except Exception as e:
        pass

RATE_LIMIT = 60
WINDOW = 60  # 60 req / minute

def is_rate_limited(ip: str):
    key = f"rate:{ip}"

    try:
        current = r.incr(key)

        if current == 1:
            r.expire(key, WINDOW)

        if current > RATE_LIMIT:
            return True

        return False

    except Exception:
        return False