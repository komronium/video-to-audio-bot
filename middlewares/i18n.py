from aiogram import BaseMiddleware
from aiogram.types import Message


class I18nMiddleware(BaseMiddleware):
    async def __call__(
            self,
            handler,
            event,
            data
    ):
        lang = event.from_user.language_code or 'en'
        data['lang'] = lang
        return await handler(event, data)
