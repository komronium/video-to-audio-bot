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
        types.InlineKeyboardButton(text=i18n.get_text('lang', lang), callback_data=f"setlang:{lang}")
        for lang in i18n.LANGUAGES
    ]
    buttons = [buttons[i : i + 2] for i in range(0, len(buttons), 2)]
    return types.InlineKeyboardMarkup(inline_keyboard=buttons)


def get_menu_keyboard(lang: str, is_admin: bool = False):
    rows = [
        [
            types.KeyboardButton(text=i18n.get_text('lang-button', lang)),
            types.KeyboardButton(text=i18n.get_text('stats-button', lang)),
            types.KeyboardButton(text=i18n.get_text('profile-button', lang))
        ],
    ]
    if is_admin:
        rows.append([types.KeyboardButton(text="Admin")])
    return types.ReplyKeyboardMarkup(keyboard=rows, resize_keyboard=True)


@router.message(Command('start'))
async def command_start(message: types.Message, db: AsyncSession):
    service = UserService(db)
    lang = await service.get_lang(message.from_user.id)

    if not lang:
        return await message.answer(
            i18n.get_text('choose_language'),
            reply_markup=get_language_keyboard()
        )

    

    await message.reply(
        i18n.get_text('start', lang),
        reply_markup=get_menu_keyboard(lang, is_admin=(message.from_user.id == settings.ADMIN_ID))
    )
    return None


async def check_subscription(bot, user_id, channel_id=settings.CHANNEL_ID):
    try:
        member = await bot.get_chat_member(channel_id, user_id)
        is_subscribed = member.status not in ['left', 'kicked', 'banned']
        return is_subscribed
    except TelegramAPIError as e:
        logging.error(f"Error while checking subscription: {e}")
        raise

def subscription_keyboard(lang: str):
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=i18n.get_text('join-channel', lang), url=settings.CHANNEL_JOIN_LINK)],
        [InlineKeyboardButton(text=i18n.get_text('check-subs', lang), callback_data='check_subscription')]
    ])
    return keyboard


@router.callback_query(F.data.startswith('setlang:'))
async def buy_diamonds_callback(call: CallbackQuery, bot: Bot):
    lang = call.data.split(':')[1]
    async with get_db() as db:
        service = UserService(db)
        await service.set_lang(call.from_user.id, lang)
        await call.answer()

    # is_subscribed = await check_subscription(bot, call.from_user.id)
    # if not is_subscribed:
    #     await call.message.delete()
    #     await call.message.answer(
    #         i18n.get_text('subscribe', lang),
    #         reply_markup=subscription_keyboard(lang)
    #     )
    #     return None

    

    await call.message.answer(
        i18n.get_text('start', lang),
        reply_markup=get_menu_keyboard(lang, is_admin=(call.from_user.id == settings.ADMIN_ID))
    )
    return await call.message.delete()


@router.message(F.text.in_([
    i18n.get_text('lang-button', lang) for lang in i18n.LANGUAGES
]))
async def command_start(message: types.Message, db: AsyncSession):
    service = UserService(db)
    lang = await service.get_lang(message.from_user.id)

    return await message.answer(
        i18n.get_text('choose_language', lang),
        reply_markup=get_language_keyboard()
    )
