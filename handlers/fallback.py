from aiogram import F, Router, types
from sqlalchemy.ext.asyncio import AsyncSession

from services.user_service import UserService
from utils.i18n import i18n

router = Router()


# Catch-all for private chats only: anything not handled by an earlier router
# (random text, a photo, sticker, audio, voice, an unsupported link…) gets a
# friendly nudge instead of silence. Must be registered LAST. Groups are left
# alone so the bot never spams them.
@router.message(F.chat.type == "private")
async def unsupported_message(message: types.Message, db: AsyncSession):
    lang = await UserService(db).get_lang(message.from_user.id)
    await message.answer(i18n.get_text("unsupported", lang))
