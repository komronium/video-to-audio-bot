import logging

from aiogram import Bot
from cachetools import TTLCache

from config import settings

# A given alert category is sent at most once per TTL window, so a recurring
# failure (rate-limit, IP block, network timeout hit by many users) can no
# longer flood the admin chat with hundreds of identical messages.
_recent: TTLCache = TTLCache(maxsize=512, ttl=600)


async def notify_admin(bot: Bot, text: str, dedupe_key: str | None = None) -> bool:
    key = dedupe_key or text[:120]
    if key in _recent:
        return False
    _recent[key] = True
    try:
        await bot.send_message(settings.ADMIN_ID, text)
        return True
    except Exception:
        logging.error(f"Failed to notify admin: {text}")
        return False
