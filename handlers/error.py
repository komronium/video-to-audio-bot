import asyncio
import logging
from aiogram import Router
from aiogram.types import ErrorEvent
from aiogram.exceptions import (
    TelegramForbiddenError,
    TelegramRetryAfter,
    TelegramAPIError
)

router = Router()


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
        return True

    logging.exception(f'Unexpected error: {error.exception}')
    return False
