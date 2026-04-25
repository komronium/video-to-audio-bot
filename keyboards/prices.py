from aiogram.utils.keyboard import InlineKeyboardBuilder

from config import settings
from utils.i18n import i18n

PRICES = settings.DIAMONDS_PRICES


def get_prices_keyboard(lang: str):
    builder = InlineKeyboardBuilder()
    for diamonds, stars in PRICES.items():
        if diamonds == 10:
            badge = f" 🔥 {i18n.get_text('popular-badge', lang)}"
        elif diamonds == 50:
            badge = f" · {i18n.get_text('save-30-badge', lang)}"
        else:
            badge = ""
        builder.button(
            text=f"{diamonds} 💎  →  {stars} ⭐️{badge}",
            callback_data=f"diamond:buy:{diamonds}",
        )
    builder.button(text="⬅️ Back", callback_data="diamond:back")
    builder.adjust(1)
    return builder.as_markup()
