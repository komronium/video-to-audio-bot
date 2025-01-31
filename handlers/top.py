from aiogram import types, Router
from aiogram.filters import Command
from sqlalchemy.orm import Session

from services.user_service import UserService

router = Router()


@router.message(Command('top'))
async def command_top(message: types.Message, db: Session):
    user_service = UserService(db)
    top_users = user_service.get_top_users()

    if not top_users:
        await message.answer("🚀 No top users yet.")
        return

    text = "🏆 <b>Top 10 Users by Activity:</b>\n\n"
    for idx, user in enumerate(top_users, start=1):
        text += f"🔹 {idx}. <b>{user.name}</b> – {user.conversation_count}\n"

    await message.bot.send_chat_action(message.chat.id, 'typing')
    await message.answer(text)
