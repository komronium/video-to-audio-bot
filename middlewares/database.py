from aiogram import BaseMiddleware

from database.session import get_db
from services.user_service import UserService


class DatabaseMiddleware(BaseMiddleware):

    async def __call__(self, handler, event, data):
        async with get_db() as db:
            data["db"] = db
            user_service = UserService(db)
            tg_user = event.from_user

            if not await user_service.is_user_exists(tg_user.id):
                await user_service.add_user(
                    tg_user.id,
                    tg_user.username,
                    tg_user.first_name,
                    tg_user.language_code or "en",
                    event.bot,
                )

            return await handler(event, data)
