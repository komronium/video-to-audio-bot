import logging

from aiogram import types, Router, F, Bot
from aiogram.exceptions import TelegramAPIError
from aiogram.filters import Command
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from sqlalchemy.ext.asyncio import AsyncSession

from config import settings
from database.session import get_db
from services.user_service import UserService
from utils.i18n import i18n

router = Router()


def get_language_keyboard():
    buttons = [
        types.InlineKeyboardButton(text=i18n.get_text("lang", lang), callback_data=f"setlang:{lang}")
        for lang in i18n.LANGUAGES
    ]
    rows = [buttons[i: i + 2] for i in range(0, len(buttons), 2)]
    return types.InlineKeyboardMarkup(inline_keyboard=rows)


def get_menu_keyboard(lang: str, is_admin: bool = False):
    rows = [
        [
            types.KeyboardButton(text=i18n.get_text("stats-button", lang)),
            types.KeyboardButton(text=i18n.get_text("profile-button", lang)),
        ],
        [
            types.KeyboardButton(text=i18n.get_text("diamonds-button", lang)),
            types.KeyboardButton(text=i18n.get_text("top-button", lang)),
        ],
        [
            types.KeyboardButton(text=i18n.get_text("lang-button", lang)),
            types.KeyboardButton(text=i18n.get_text("help-button", lang)),
        ],
    ]
    if is_admin:
        rows.append([types.KeyboardButton(text="Admin")])
    return types.ReplyKeyboardMarkup(keyboard=rows, resize_keyboard=True)


@router.message(Command("start"))
async def command_start(message: types.Message, db: AsyncSession):
    service = UserService(db)
    lang = await service.get_lang(message.from_user.id)
    referral_code = None

    args = message.text.split()
    if len(args) > 1:
        referral_code = args[1].upper()

    if not lang:
        if referral_code:
            async with get_db() as db2:
                await UserService(db2).apply_referral(message.from_user.id, referral_code)
        return await message.answer(
            i18n.get_text("choose_language"),
            reply_markup=get_language_keyboard(),
        )

    if referral_code:
        applied = await service.apply_referral(message.from_user.id, referral_code)
        await message.answer(
            i18n.get_text("referral-applied", lang)
            if applied
            else i18n.get_text("referral-invalid", lang)
        )

    await message.reply(
        i18n.get_text("start", lang),
        reply_markup=get_menu_keyboard(lang, is_admin=(message.from_user.id == settings.ADMIN_ID)),
    )


@router.callback_query(F.data.startswith("setlang:"))
async def set_language_callback(call: CallbackQuery):
    lang = call.data.split(":")[1]
    async with get_db() as db:
        await UserService(db).set_lang(call.from_user.id, lang)
    await call.answer()
    await call.message.answer(
        i18n.get_text("start", lang),
        reply_markup=get_menu_keyboard(lang, is_admin=(call.from_user.id == settings.ADMIN_ID)),
    )
    try:
        await call.message.delete()
    except TelegramAPIError:
        pass


@router.message(F.text.in_([i18n.get_text("lang-button", lang) for lang in i18n.LANGUAGES]))
async def language_button_handler(message: types.Message, db: AsyncSession):
    service = UserService(db)
    lang = await service.get_lang(message.from_user.id)
    await message.answer(
        i18n.get_text("choose_language", lang),
        reply_markup=get_language_keyboard(),
    )
