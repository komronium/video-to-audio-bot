import logging
from datetime import date, timedelta

from redis.exceptions import RedisError

from services.redis_client import redis_client as _redis

# Streak milestone → diamond reward
STREAK_REWARDS: dict[int, int] = {3: 1, 7: 3, 14: 5, 30: 10}


async def update_streak(user_id: int) -> tuple[int, int]:
    """
    Call once per successful conversion.
    Returns (streak_days, reward_diamonds).
    reward_diamonds > 0 only on milestone days.
    Fails open: if Redis is down, returns (0, 0) instead of raising.
    """
    try:
        today = date.today().isoformat()
        yesterday = (date.today() - timedelta(days=1)).isoformat()

        date_key = f"streak:date:{user_id}"
        count_key = f"streak:count:{user_id}"

        last_date = await _redis.get(date_key)

        if last_date == today:
            # Already counted today, return current streak without reward
            streak = int(await _redis.get(count_key) or 1)
            return streak, 0

        if last_date == yesterday:
            streak = await _redis.incr(count_key)
        else:
            # Gap or first time
            await _redis.set(count_key, 1)
            streak = 1

        await _redis.set(date_key, today)
        reward = STREAK_REWARDS.get(streak, 0)
        return streak, reward
    except RedisError:
        logging.warning("Redis unavailable, skipping streak update")
        return 0, 0


async def get_streak(user_id: int) -> int:
    try:
        val = await _redis.get(f"streak:count:{user_id}")
        return int(val or 0)
    except RedisError:
        return 0
