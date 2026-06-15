import logging

from aiogram import types, Router, F, Bot
from aiogram.exceptions import TelegramAPIError
from aiogram.filters import Command
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from sqlalchemy.ext.asyncio import AsyncSession

from config import settings
from database.session import get_db
from services.user_service import UserService
from utils.daily_limit import DAILY_LIMIT, get_daily_count
from utils.i18n import i18n
from utils.onboarding import maybe_send_demo

router = Router()


def get_language_keyboard(current: str | None = None):
    buttons = [
        types.InlineKeyboardButton(
            text=("✅ " if lang == current else "") + i18n.get_text("lang", lang),
            callback_data=f"setlang:{lang}",
        )
        for lang in i18n.LANGUAGES
    ]
    rows = [buttons[i: i + 2] for i in range(0, len(buttons), 2)]
    return types.InlineKeyboardMarkup(inline_keyboard=rows)


async def _status_line(user, lang: str) -> str:
    if user.is_premium:
        return i18n.get_text("start-status-premium", lang)
    if user.is_active_premium:
        # Active monthly subscription — show expiry so renewal is on the radar
        return i18n.get_text("start-status-subscription", lang).format(
            until=user.subscription_until.strftime("%d %b"),
        )
    used = await get_daily_count(user.user_id)
    return i18n.get_text("start-status", lang).format(
        left=max(DAILY_LIMIT - used, 0),
        limit=DAILY_LIMIT,
        diamonds=user.diamonds or 0,
    )


def get_menu_keyboard(lang: str, is_admin: bool = False):
    # Keep the menu to what an end user actually needs. Sending a video needs
    # no button; we surface diamonds + invite (the growth lever) prominently
    # and keep profile/help/language one tap away. Stats/Top stay as commands.
    rows = [
        [
            types.KeyboardButton(text=i18n.get_text("diamonds-button", lang)),
            types.KeyboardButton(text=i18n.get_text("invite-friend", lang)),
        ],
        [
            types.KeyboardButton(text=i18n.get_text("profile-button", lang)),
            types.KeyboardButton(text=i18n.get_text("help-button", lang)),
        ],
        [
            types.KeyboardButton(text=i18n.get_text("lang-button", lang)),
        ],
    ]
    if is_admin:
        rows.append([types.KeyboardButton(text="Admin")])
    return types.ReplyKeyboardMarkup(
        keyboard=rows,
        resize_keyboard=True,
        input_field_placeholder=i18n.get_text("menu-placeholder", lang),
    )


@router.message(Command("start"))
async def command_start(message: types.Message, db: AsyncSession):
    service = UserService(db)
    user = await service.get_user(message.from_user.id)
    # Show the language picker until the user has explicitly chosen a
    # supported language (auto-detected unsupported codes don't count)
    lang = user.lang if user and user.lang in i18n.LANGUAGES else None
    referral_code = None

    args = message.text.split()
    if len(args) > 1:
        arg = args[1]
        # `src_<tag>` (or just `src-<tag>`) marks acquisition source so we can
        # tell which channels bring users that actually retain. Anything else
        # is treated as a referral code (existing behaviour).
        if arg.lower().startswith(("src_", "src-")):
            await service.set_source(message.from_user.id, arg[4:])
        else:
            referral_code = arg.upper()

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

    text = i18n.get_text("start", lang) + "\n\n" + await _status_line(user, lang)
    await message.answer(
        text,
        reply_markup=get_menu_keyboard(lang, is_admin=(message.from_user.id == settings.ADMIN_ID)),
    )


@router.callback_query(F.data.startswith("setlang:"))
async def set_language_callback(call: CallbackQuery):
    lang = call.data.split(":")[1]
    async with get_db() as db:
        service = UserService(db)
        await service.set_lang(call.from_user.id, lang)
        user = await service.get_user(call.from_user.id)
    await call.answer()
    text = i18n.get_text("start", lang)
    if user:
        text += "\n\n" + await _status_line(user, lang)
    await call.message.answer(
        text,
        reply_markup=get_menu_keyboard(lang, is_admin=(call.from_user.id == settings.ADMIN_ID)),
    )
    try:
        await call.message.delete()
    except TelegramAPIError:
        pass
    # First-time arrivals get a one-shot demo MP3 so the value prop is obvious
    # before they upload anything themselves. Idempotent.
    await maybe_send_demo(call.bot, call.message.chat.id, call.from_user.id, lang)


@router.message(Command("lang"))
@router.message(F.text.in_([i18n.get_text("lang-button", lang) for lang in i18n.LANGUAGES]))
async def language_button_handler(message: types.Message, db: AsyncSession):
    service = UserService(db)
    lang = await service.get_lang(message.from_user.id)
    await message.answer(
        i18n.get_text("choose_language", lang),
        reply_markup=get_language_keyboard(current=lang),
    )
