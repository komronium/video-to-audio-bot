from aiogram import BaseMiddleware

from database.session import get_db
from services.user_service import UserService
from utils.i18n import i18n


class DatabaseMiddleware(BaseMiddleware):

    async def __call__(self, handler, event, data):
        async with get_db() as db:
            data["db"] = db
            user_service = UserService(db)
            tg_user = event.from_user

            if not await user_service.is_user_exists(tg_user.id):
                # Only store supported languages; None makes /start show the
                # language picker instead of silently falling back to English
                lang_code = (tg_user.language_code or "")[:2]
                lang = lang_code if lang_code in i18n.LANGUAGES else None
                await user_service.add_user(
                    tg_user.id,
                    tg_user.username,
                    tg_user.first_name,
                    lang,
                    event.bot,
                )

            return await handler(event, data)
