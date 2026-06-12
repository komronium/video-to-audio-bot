from aiogram import BaseMiddleware
from cachetools import TTLCache

from utils.i18n import i18n


class ThrottlingMiddleware(BaseMiddleware):

    def __init__(self, rate_limit: float = 0.5):
        self.rate_limit = rate_limit
        # value = whether the user has already been warned this window
        self.cache = TTLCache(maxsize=10000, ttl=rate_limit)
        super().__init__()

    async def __call__(self, handler, event, data):
        user_id = event.from_user.id

        if user_id in self.cache:
            # Warn once per window, then drop silently — replying to every
            # flooded message would make the bot flood itself
            if not self.cache[user_id]:
                self.cache[user_id] = True
                lang = (event.from_user.language_code or "en")[:2]
                await event.answer(i18n.get_text("throttled", lang))
            return None

        self.cache[user_id] = False
        return await handler(event, data)
