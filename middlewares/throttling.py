from aiogram import BaseMiddleware
from datetime import datetime
from cachetools import TTLCache


class ThrottlingMiddleware(BaseMiddleware):

    def __init__(self, rate_limit: float = 0.5):
        self.rate_limit = rate_limit
        self.cache = TTLCache(maxsize=10000, ttl=rate_limit)
        super().__init__()

    async def __call__(
            self,
            handler,
            event,
            data
    ):
        user_id = event.from_user.id

        if user_id in self.cache:
            await event.answer('Too many requests! Please wait.')
            return None

        self.cache[user_id] = datetime.now()
        return await handler(event, data)
