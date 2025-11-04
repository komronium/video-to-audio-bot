from aiogram import BaseMiddleware

from config import settings
from database.session import get_db
from services.user_service import UserService

LANGS = dict({})
count = 0


class DatabaseMiddleware(BaseMiddleware):

    async def __call__(
            self,
            handler,
            event,
            data
    ):
        async with get_db() as db:
            data['db'] = db
            user_service = UserService(db)

            user_id = event.from_user.id
            username = event.from_user.username
            name = event.from_user.first_name
            lang = event.from_user.language_code

            if not await user_service.is_user_exists(user_id):
                await user_service.add_user(user_id, username, name, lang, event.bot)

            return await handler(event, data)
