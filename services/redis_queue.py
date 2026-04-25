import redis.asyncio as aioredis


class QueueManager:
    def __init__(self):
        self._redis = aioredis.Redis(host="localhost", port=6379, decode_responses=True)
        self.queue_key = "conversion_queue"

    def _entry(self, user_id: int, file_id: str, timestamp: int) -> str:
        return f"{user_id}:{file_id}:{timestamp}"

    async def add_to_queue(self, user_id: int, file_id: str, timestamp: int) -> int:
        entry = self._entry(user_id, file_id, timestamp)
        await self._redis.rpush(self.queue_key, entry)
        return await self.get_queue_position(user_id, file_id, timestamp)

    async def get_queue_position(self, user_id: int, file_id: str, timestamp: int) -> int:
        entry = self._entry(user_id, file_id, timestamp)
        queue = await self._redis.lrange(self.queue_key, 0, -1)
        for i, item in enumerate(queue):
            if item == entry:
                return i + 1
        return 0

    async def remove_from_queue(self, user_id: int, file_id: str, timestamp: int):
        await self._redis.lrem(self.queue_key, 0, self._entry(user_id, file_id, timestamp))

    async def queue_length(self) -> int:
        return await self._redis.llen(self.queue_key)

    async def user_in_queue(self, user_id: int) -> bool:
        queue = await self._redis.lrange(self.queue_key, 0, -1)
        prefix = f"{user_id}:"
        return any(item.startswith(prefix) for item in queue)

    async def clear_queue(self):
        await self._redis.delete(self.queue_key)


queue_manager = QueueManager()
