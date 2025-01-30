from aiogram import BaseMiddleware
from aiogram.types import Update
from sqlalchemy.orm import Session

from database.session import get_db
from services.user_service import UserService


class DatabaseMiddleware(BaseMiddleware):

    async def __call__(
            self,
            handler,
            event,
            data
    ):
        db: Session = next(get_db())
        data['db'] = db
        user_service = UserService(db)

        user_id = event.from_user.id
        username = event.from_user.username
        name = event.from_user.first_name

        if not user_service.is_user_exists(user_id):
            await user_service.add_user(user_id, username, name, event.bot)

        return await handler(event, data)
