from aiogram import types, Router
from aiogram.filters import Command
from sqlalchemy.ext.asyncio import AsyncSession

from services.user_service import UserService
from utils.i18n import i18n

router = Router()


def get_language_keyboard():
    buttons = [
        [types.InlineKeyboardButton(text=name, callback_data=f"setlang:{code}")]
        for code, name in i18n.LANGUAGES.items()
    ]
    return types.InlineKeyboardMarkup(inline_keyboard=buttons)


@router.message(Command('start'))
async def command_start(message: types.Message, db: AsyncSession):
    service = UserService(db)
    lang = await service.get_lang(message.from_user.id)

    if not lang:
        await message.answer(
            i18n.get_text('choose_language'),
            reply_markup=get_language_keyboard()
        )

    await message.reply(i18n.get_text('start', lang))
