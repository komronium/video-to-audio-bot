from aiogram import types, Router, F
from sqlalchemy.ext.asyncio import AsyncSession

from services.user_service import UserService
from utils.i18n import i18n

EMOJIES = ['1️⃣', '2️⃣', '3️⃣', '4️⃣', '5️⃣', '6️⃣', '7️⃣', '8️⃣', '9️⃣', '🔟']

router = Router()


@router.message(F.text.in_([
    i18n.get_text('top-button', lang) for lang in i18n.LANGUAGES
]))
async def command_top(message: types.Message, db: AsyncSession):
    user_service = UserService(db)
    top_users = await user_service.get_top_users()

    if not top_users:
        await message.answer("🚀 No top users yet.")
        return

    text = "🏆 <b>TOP 10 MOST ACTIVE USERS:</b>\n\n"
    for idx, user in enumerate(top_users):
        text += f"{EMOJIES[idx]}  <b>{user.name}</b> – {user.conversation_count}\n"

    await message.answer(text)
