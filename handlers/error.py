import logging
from aiogram import Router
from aiogram.exceptions import TelegramForbiddenError

router = Router()


@router.error()
async def errors_handler(update, exception):

    if isinstance(exception, TelegramForbiddenError):
        logging.exception(exception.message)
        return True

    logging.exception(f'Update: {update} \n{exception}')
