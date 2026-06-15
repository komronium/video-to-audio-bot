import logging

from aiogram import Bot
from aiogram.exceptions import TelegramAPIError
from redis.exceptions import RedisError

from config import settings
from services.redis_client import redis_client
from utils.i18n import i18n

_DEMO_FLAG_TTL = 60 * 60 * 24 * 365  # 1 year — effectively "once per user"


async def maybe_send_demo(bot: Bot, chat_id: int, user_id: int, lang: str) -> None:
    """Send the cached demo MP3 the first time a user picks a language.

    Idempotent via Redis flag. Silently skips if no demo file_id is configured
    or if Redis is down (the demo is a nice-to-have, never block onboarding).
    """
    if not settings.ONBOARDING_DEMO_FILE_ID:
        return
    flag_key = f"demo_seen:{user_id}"
    try:
        # NX so concurrent /start clicks don't double-send
        was_set = await redis_client.set(flag_key, "1", ex=_DEMO_FLAG_TTL, nx=True)
        if not was_set:
            return
    except RedisError:
        logging.warning("Redis unavailable, skipping onboarding demo")
        return

    try:
        await bot.send_audio(
            chat_id,
            settings.ONBOARDING_DEMO_FILE_ID,
            caption=i18n.get_text("demo-caption", lang),
        )
    except TelegramAPIError as e:
        logging.warning(f"Onboarding demo send failed for user {user_id}: {e}")
        # Roll back the flag so the user gets another chance next time
        try:
            await redis_client.delete(flag_key)
        except RedisError:
            pass
