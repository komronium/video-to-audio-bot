from aiogram import types, Router, F
from sqlalchemy.ext.asyncio import AsyncSession

from services.user_service import UserService
from utils.i18n import i18n

router = Router()

NOT_REGISTERED_TEXT = "⚠️ You are not registered in the system."


@router.message(F.text.in_([
    i18n.get_text('profile-button', lang) for lang in i18n.LANGUAGES
]))
async def profile_handler(message: types.Message, db: AsyncSession):
    user_service = UserService(db)
    user = await user_service.get_user(message.from_user.id)
    lang = await user_service.get_lang(message.from_user.id)

    if not user:
        return await message.answer(NOT_REGISTERED_TEXT)

    text = i18n.get_text('profile', lang).format(
        user_id=user.user_id,
        name=user.name,
        username=user.username or 'N/A',
        conversation_count=user.conversation_count,
        joined_at=user.joined_at.strftime('%d-%m-%Y')
    )

    return await message.answer(text.strip())
