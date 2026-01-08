from aiogram.utils.keyboard import InlineKeyboardBuilder

from config import settings
from utils.i18n import i18n

PRICES = settings.DIAMONDS_PRICES


def get_prices_keyboard(lang):
    builder = InlineKeyboardBuilder()
    for price in PRICES:
        builder.button(
            text=f"{price} " + i18n.get_text("diamonds-button") + f" →  {PRICES[price]} ⭐️", lang,
            callback_data=f"diamond:buy:{price}",
        )
    builder.button(text=i18n.get_text("⬅️ Back", lang), callback_data="diamond:back")
    builder.adjust(1)
    return builder.as_markup()
