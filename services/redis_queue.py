import redis


class QueueManager:
    def __init__(self):
        self.redis_client = redis.Redis(
            host='localhost',
            port=6379,
            decode_responses=True
        )
        self.queue_key = "conversion_queue"

    def add_to_queue(self, user_id: int, file_id: str, timestamp: int) -> int:
        self.redis_client.rpush(self.queue_key, f"{user_id}:{file_id}:{timestamp}")
        return self.get_queue_position(user_id, file_id, timestamp)

    def get_queue_position(self, user_id: int, file_id: str, timestamp: int) -> int:
        queue = self.redis_client.lrange(self.queue_key, 0, -1)
        for i, item in enumerate(queue):
            if item == f"{user_id}:{file_id}:{timestamp}":
                return i + 1
        return 0

    def remove_from_queue(self, user_id: int, file_id: str, timestamp: int):
        queue = self.redis_client.lrange(self.queue_key, 0, -1)
        for item in queue:
            if item == f"{user_id}:{file_id}:{timestamp}":
                self.redis_client.lrem(self.queue_key, 0, item)

    def get_next_task(self) -> tuple:
        task = self.redis_client.lpop(self.queue_key)
        if task:
            user_id, file_id = task.split(":")
            return int(user_id), file_id
        return None, None

    def queue_length(self) -> int:
        return self.redis_client.llen(self.queue_key)
    
    def clear_queue(self):
        self.redis_client.delete(self.queue_key)


queue_manager = QueueManager()
queue_manager.clear_queue()
