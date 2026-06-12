import asyncio
import logging

from aiogram import Bot, Router
from aiogram.types import ErrorEvent
from aiogram.exceptions import (
    TelegramForbiddenError,
    TelegramRetryAfter,
    TelegramAPIError
)
from cachetools import TTLCache
from redis.exceptions import RedisError

from config import settings

router = Router()

# Same error notified at most once per 10 minutes — a recurring failure
# (e.g. Redis down) must not flood the admin chat with thousands of messages
_recently_notified: TTLCache = TTLCache(maxsize=256, ttl=600)


async def _notify_admin(bot: Bot, text: str, dedupe_key: str | None = None):
    key = dedupe_key or text[:120]
    if key in _recently_notified:
        return
    _recently_notified[key] = True
    try:
        await bot.send_message(settings.ADMIN_ID, text)
    except Exception:
        logging.error(f"Failed to notify admin: {text}")


@router.error()
async def errors_handler(error: ErrorEvent):
    exc = error.exception

    if isinstance(exc, TelegramForbiddenError):
        logging.warning(f"Bot was blocked by user: {exc.message}")
        return True

    if isinstance(exc, TelegramRetryAfter):
        logging.info(f"Flood control exceeded. Sleeping for {exc.retry_after} seconds.")
        await asyncio.sleep(exc.retry_after)
        return True

    if isinstance(exc, RedisError):
        logging.error(f"Redis error: {exc}")
        await _notify_admin(
            error.update.bot,
            "<b>🔴 Redis is unreachable</b>\n"
            f"<code>{type(exc).__name__}: {exc}</code>\n\n"
            "Check the server: <code>systemctl status redis</code> / "
            "<code>journalctl -u redis -n 50</code>",
            dedupe_key="redis-down",
        )
        return True

    if isinstance(exc, TelegramAPIError):
        logging.error(f"Telegram API Error: {exc.message}")
        await _notify_admin(
            error.update.bot,
            f"<b>⚠️ Telegram API Error</b>\n<code>{exc.message}</code>",
            dedupe_key=f"tg:{type(exc).__name__}:{exc.message[:80]}",
        )
        return True

    logging.exception(f'Unexpected error: {exc}')
    await _notify_admin(
        error.update.bot,
        f"<b>🔴 Unexpected error</b>\n<code>{type(exc).__name__}: {exc}</code>",
        dedupe_key=f"unexpected:{type(exc).__name__}:{str(exc)[:80]}",
    )
    return False
