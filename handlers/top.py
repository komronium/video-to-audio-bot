from aiogram import F, Router, types
from sqlalchemy.ext.asyncio import AsyncSession

from services.user_service import UserService
from utils.i18n import i18n

EMOJIES = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]

router = Router()


@router.message(
    F.text.in_([i18n.get_text("top-button", lang) for lang in i18n.LANGUAGES])
)
async def command_top(message: types.Message, db: AsyncSession):
    user_service = UserService(db)
    lang = await user_service.get_lang(message.from_user.id)
    top_users = await user_service.get_top_users()

    if not top_users:
        await message.answer(i18n.get_text("top-empty", lang))
        return

    text = i18n.get_text("top-title", lang) + "\n\n"
    for idx, user in enumerate(top_users):
        text += f"{EMOJIES[idx]}  <b>{user.name}</b> – {user.conversation_count}\n"

    await message.answer(text)


async def rank_internal(message: types.Message, db: AsyncSession):
    service = UserService(db)
    lang = await service.get_lang(message.from_user.id)
    user = await service.get_user(message.from_user.id)
    if not user:
        await message.answer(i18n.get_text("not-registered", lang))
        return
    rank = await service.get_user_rank(user.user_id)
    await message.answer(
        i18n.get_text("rank-text", lang).format(rank=rank, conversions=user.conversation_count)
    )
