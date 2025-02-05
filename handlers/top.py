from aiogram import types, Router
from aiogram.filters import Command
from sqlalchemy.ext.asyncio import AsyncSession

from services.user_service import UserService

EMOJIES = '1️⃣2️⃣3️⃣4️⃣5️⃣6️⃣7️⃣8️⃣9️⃣🔟'

router = Router()


@router.message(Command('top'))
async def command_top(message: types.Message, db: AsyncSession):
    user_service = UserService(db)
    top_users = await user_service.get_top_users()

    if not top_users:
        await message.answer("🚀 No top users yet.")
        return

    text = "🏆 <b>TOP 10 MOST ACTIVE USERS:</b>\n\n"
    for idx, user in enumerate(top_users):
        text += f"{EMOJIES[idx]}  <b>{user.name}</b> – {user.conversation_count}\n"

    await message.bot.send_chat_action(message.chat.id, 'typing')
    await message.answer(text)
