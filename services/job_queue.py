import json

from services.redis_client import redis_client

PENDING_KEY = "jobs:pending"
PROCESSING_KEY = "jobs:processing"


class JobQueue:
    """Persistent FIFO job queue on Redis lists.

    Producers LPUSH onto `jobs:pending`; workers BRPOPLPUSH the oldest entry
    into `jobs:processing` and LREM it after finishing. Anything still in
    `jobs:processing` after a crash/restart is moved back by requeue_orphans(),
    so accepted jobs are never silently lost.
    (BRPOPLPUSH instead of BLMOVE so Redis < 6.2 also works.)
    """

    async def enqueue(self, job: dict) -> int:
        return await redis_client.lpush(PENDING_KEY, json.dumps(job))

    async def reserve(self, timeout: int = 5) -> tuple[str, dict] | None:
        raw = await redis_client.brpoplpush(PENDING_KEY, PROCESSING_KEY, timeout)
        if raw is None:
            return None
        return raw, json.loads(raw)

    async def ack(self, raw: str):
        await redis_client.lrem(PROCESSING_KEY, 1, raw)

    async def pending_count(self) -> int:
        return await redis_client.llen(PENDING_KEY)

    async def user_has_job(self, user_id: int) -> bool:
        for key in (PENDING_KEY, PROCESSING_KEY):
            for raw in await redis_client.lrange(key, 0, -1):
                try:
                    if json.loads(raw).get("user_id") == user_id:
                        return True
                except json.JSONDecodeError:
                    continue
        return False

    async def requeue_orphans(self) -> int:
        count = 0
        while True:
            raw = await redis_client.rpop(PROCESSING_KEY)
            if raw is None:
                break
            try:
                job = json.loads(raw)
                job["attempts"] = job.get("attempts", 0) + 1
                raw = json.dumps(job)
            except json.JSONDecodeError:
                continue
            # RPUSH: orphans are the oldest jobs, serve them first
            await redis_client.rpush(PENDING_KEY, raw)
            count += 1
        return count


job_queue = JobQueue()
