from aiogram import types, Router
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

router = Router()


@router.message(Command('premium'))
async def premium_info(message: types.Message):
    markup = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text='👑 Get Premium', url='https://t.me/TGBots_ContactBot')]
    ])

    text = (
        "<b>🚀 Premium Version Available!</b>\n"
        "Unlock unlimited conversions and process videos up to <b>2GB</b>.\n\n"
        "Price: <b>$5 (lifetime)</b>\n"
        "Contact: @TGBots_ContactBot"
    )

    await message.answer(text, reply_markup=markup)
