from aiogram import BaseMiddleware
from aiogram.types import Message


class I18nMiddleware(BaseMiddleware):
    async def __call__(
            self,
            handler,
            event,
            data
    ):
        return await handler(event, data)

    async def on_pre_process_message(self, message: Message, data: dict):
        # Foydalanuvchi tilini aniqlash (masalan, Telegram til kodi)
        lang = message.from_user.language_code or 'en'
        data['lang'] = lang
