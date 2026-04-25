from aiogram.utils.keyboard import InlineKeyboardBuilder

from config import settings
from utils.i18n import i18n

PRICES = settings.DIAMONDS_PRICES


def get_prices_keyboard(lang: str):
    builder = InlineKeyboardBuilder()
    for diamonds, stars in PRICES.items():
        save_badge = f" • {i18n.get_text('save-30-badge', lang)}" if diamonds == 50 else ""
        label = i18n.get_text("diamonds-button", lang)
        builder.button(
            text=f"{diamonds} {label} →  {stars} ⭐️{save_badge}",
            callback_data=f"diamond:buy:{diamonds}",
        )
    builder.button(text="⬅️ Back", callback_data="diamond:back")
    builder.adjust(1)
    return builder.as_markup()
