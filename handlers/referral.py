from aiogram import F, Router
from aiogram.types import Message
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy.ext.asyncio import AsyncSession

from config import settings
from services.user_service import UserService
from utils.i18n import i18n

router = Router()


@router.message(F.text.startswith("/referral"))
async def referral_command(message: Message, db: AsyncSession):
    user_id = message.from_user.id
    user_service = UserService(db)
    user = await user_service.get_user(user_id)

    if not user:
        fallback_lang = (message.from_user.language_code or "en")[:2]
        if fallback_lang not in i18n.LANGUAGES:
            fallback_lang = "en"
        await message.answer(i18n.get_text("referral-first-start", fallback_lang))
        return

    lang = user.lang or "en"
    code = await user_service.generate_referral_code(user_id)

    bot_username = (await message.bot.get_me()).username
    referral_link = f"https://t.me/{bot_username}?start={code}"

    builder = InlineKeyboardBuilder()
    builder.button(
        text=i18n.get_text("referral-share", lang),
        url=f"https://t.me/share/url?url={referral_link}",
    )
    builder.adjust(1)

    await message.answer(
        i18n.get_text("referral-info", lang).format(link=referral_link),
        reply_markup=builder.as_markup(),
    )
