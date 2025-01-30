from aiogram import types, Router
from aiogram.filters import Command
from sqlalchemy.orm import Session

from services.user_service import UserService

router = Router()


@router.message(Command('profile'))
async def profile_handler(message: types.Message, db: Session):
    user_service = UserService(db)
    user = user_service.get_user(message.from_user.id)

    if user:
        text = (
            f"👤 <b>Your Profile:</b>\n\n"
            f"🔹 User ID: <b>{user.user_id}</b>\n"
            f"🔹 Name: <b>{user.name}</b>\n"
            f"🔹 Username: @{user.username if user.username else 'N/A'}\n"
            f"🔹 Conversations: <b>{user.conversation_count}</b>\n"
            f"🔹 Joined: <b>{user.joined_at.strftime('%d-%m-%Y')}</b>"
        )
    else:
        text = "⚠️ You are not registered in the system."

    await message.answer(text)
