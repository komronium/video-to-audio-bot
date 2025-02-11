from aiogram import types, Router
from aiogram.filters import Command
from sqlalchemy.ext.asyncio import AsyncSession

from services.user_service import UserService

router = Router()

PROFILE_TEMPLATE = (
    "👤 <b>Your Profile:</b>\n\n"
    "🔹 User ID: <b>{user_id}</b>\n"
    "🔹 Name: <b>{name}</b>\n"
    "🔹 Username: @{username}\n"
    "🔹 Conversations: <b>{conversation_count}</b>\n"
    "🔹 Joined: <b>{joined_at}</b>"
)
NOT_REGISTERED_TEXT = "⚠️ You are not registered in the system."


@router.message(Command('profile'))
async def profile_handler(message: types.Message, db: AsyncSession):
    user_service = UserService(db)
    user = await user_service.get_user(message.from_user.id)

    if not user:
        return await message.answer(NOT_REGISTERED_TEXT)

    text = PROFILE_TEMPLATE.format(
        user_id=user.user_id,
        name=user.name,
        username=user.username or 'N/A',
        conversation_count=user.conversation_count,
        joined_at=user.joined_at.strftime('%d-%m-%Y')
    )

    await message.answer(text.strip())
