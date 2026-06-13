import asyncio
import logging

from aiogram import Router
from aiogram.types import ErrorEvent
from aiogram.exceptions import (
    TelegramForbiddenError,
    TelegramRetryAfter,
    TelegramAPIError,
)
from redis.exceptions import RedisError

from utils.admin_alert import notify_admin

router = Router()


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
        await notify_admin(
            error.update.bot,
            "<b>🔴 Redis is unreachable</b>\n"
            f"<code>{type(exc).__name__}: {exc}</code>\n\n"
            "Check the server: <code>systemctl status redis-server</code> / "
            "<code>journalctl -u redis-server -n 50</code>",
            dedupe_key="redis-down",
        )
        return True

    if isinstance(exc, TelegramAPIError):
        logging.error(f"Telegram API Error: {exc.message}")
        await notify_admin(
            error.update.bot,
            f"<b>⚠️ Telegram API Error</b>\n<code>{exc.message}</code>",
            dedupe_key=f"tg:{type(exc).__name__}:{exc.message[:80]}",
        )
        return True

    logging.exception(f"Unexpected error: {exc}")
    await notify_admin(
        error.update.bot,
        f"<b>🔴 Unexpected error</b>\n<code>{type(exc).__name__}: {str(exc)[:300]}</code>",
        dedupe_key=f"unexpected:{type(exc).__name__}:{str(exc)[:80]}",
    )
    return False
