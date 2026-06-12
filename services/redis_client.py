import redis.asyncio as aioredis
from redis.asyncio.retry import Retry
from redis.backoff import ExponentialBackoff
from redis.exceptions import ConnectionError as RedisConnectionError
from redis.exceptions import TimeoutError as RedisTimeoutError

# Short connect timeout + bounded retries: when Redis is down, callers get a
# fast RedisError they can degrade on, instead of hanging or crash-looping.
redis_client = aioredis.Redis(
    host="localhost",
    port=6379,
    decode_responses=True,
    socket_connect_timeout=3,
    retry=Retry(ExponentialBackoff(cap=1.0, base=0.1), 3),
    retry_on_error=[RedisConnectionError, RedisTimeoutError],
    health_check_interval=30,
)
