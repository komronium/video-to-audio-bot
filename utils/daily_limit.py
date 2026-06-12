import logging
from datetime import datetime, timedelta

from redis.exceptions import RedisError

from services.redis_client import redis_client

DAILY_LIMIT = 3


def _today_key(user_id: int) -> str:
    today = datetime.today().strftime("%Y-%m-%d")
    return f"user:{user_id}:{today}"


def seconds_until_midnight() -> int:
    now = datetime.now()
    midnight = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    return int((midnight - now).total_seconds())


async def get_daily_count(user_id: int) -> int:
    # Fails open: if Redis is down, users stay under the limit instead of the
    # bot breaking entirely.
    try:
        return int(await redis_client.get(_today_key(user_id)) or 0)
    except RedisError:
        logging.warning("Redis unavailable, daily limit check skipped")
        return 0


async def increment_daily_count(user_id: int, amount: int = 1):
    try:
        key = _today_key(user_id)
        new_value = await redis_client.incrby(key, amount)
        if new_value == amount:
            # First increment today: key dies at midnight, same as the date in its name
            await redis_client.expire(key, seconds_until_midnight())
    except RedisError:
        logging.warning("Redis unavailable, daily count not incremented")


def ttl_to_str(ttl: int) -> str:
    if ttl <= 0:
        return "soon"
    h, m = ttl // 3600, (ttl % 3600) // 60
    return f"{h}h {m}m" if h else f"{m}m"


def reset_time_str() -> str:
    return ttl_to_str(seconds_until_midnight())
