from aiogram import BaseMiddleware

from config import settings
from database.session import get_db
from services.user_service import UserService

LANGS = []
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

            if not await user_service.is_user_exists(user_id):
                await user_service.add_user(user_id, username, name, event.bot)

                lang = event.from_user.language_code
                global count, LANGS
                count += 1

                if lang in LANGS:
                    LANGS[lang] += 1
                else:
                    LANGS[lang] = 1

                if count % 10 == 0:
                    text = ''

                    for lang in LANGS:
                        text += f"<code>{lang} {LANGS[lang]}</code>\n"
                    await event.bot.send_message(settings.GROUP_ID, text)

            return await handler(event, data)
