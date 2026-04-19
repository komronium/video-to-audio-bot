import asyncio
import logging
from aiogram import Bot, Router
from aiogram.types import ErrorEvent
from aiogram.exceptions import (
    TelegramForbiddenError,
    TelegramRetryAfter,
    TelegramAPIError
)

from config import settings

router = Router()


async def _notify_admin(bot: Bot, text: str):
    try:
        await bot.send_message(settings.ADMIN_ID, text)
    except Exception:
        logging.error(f"Failed to notify admin: {text}")


@router.error()
async def errors_handler(error: ErrorEvent):

    if isinstance(error.exception, TelegramForbiddenError):
        logging.warning(f"Bot was blocked by user: {error.exception.message}")
        return True

    if isinstance(error.exception, TelegramRetryAfter):
        logging.info(f"Flood control exceeded. Sleeping for {error.exception.retry_after} seconds.")
        await asyncio.sleep(error.exception.retry_after)
        return True

    if isinstance(error.exception, TelegramAPIError):
        logging.error(f"Telegram API Error: {error.exception.message}")
        await _notify_admin(
            error.update.bot,
            f"<b>⚠️ Telegram API Error</b>\n<code>{error.exception.message}</code>",
        )
        return True

    logging.exception(f'Unexpected error: {error.exception}')
    await _notify_admin(
        error.update.bot,
        f"<b>🔴 Unexpected error</b>\n<code>{type(error.exception).__name__}: {error.exception}</code>",
    )
    return False
