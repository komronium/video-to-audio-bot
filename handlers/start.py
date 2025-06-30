from aiogram import types, Router, F
from aiogram.filters import Command
from aiogram.types import CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession

from database.session import get_db
from services.user_service import UserService
from utils.i18n import i18n

router = Router()


def get_language_keyboard():
    buttons = [
        types.InlineKeyboardButton(text=i18n.get_text('lang', lang), callback_data=f"setlang:{lang}")
        for lang in i18n.LANGUAGES
    ]
    buttons = [buttons[i : i + 2] for i in range(0, len(buttons), 2)]
    return types.InlineKeyboardMarkup(inline_keyboard=buttons)


@router.message(Command('start'))
async def command_start(message: types.Message, db: AsyncSession):
    service = UserService(db)
    lang = await service.get_lang(message.from_user.id)

    if not lang:
        return await message.answer(
            i18n.get_text('choose_language'),
            reply_markup=get_language_keyboard()
        )

    await message.reply(i18n.get_text('start', lang))
    return None


@router.callback_query(F.data.startswith('setlang:'))
async def buy_diamonds_callback(call: CallbackQuery):
    lang = call.data.split(':')[1]
    async with get_db() as db:
        service = UserService(db)
        await service.set_lang(call.from_user.id, lang)
        await call.answer()

    await call.message.edit_text(i18n.get_text('start', lang))


@router.message(Command('lang'))
async def command_start(message: types.Message, db: AsyncSession):
    service = UserService(db)
    lang = await service.get_lang(message.from_user.id)

    return await message.answer(
        i18n.get_text('choose_language', lang),
        reply_markup=get_language_keyboard()
    )
