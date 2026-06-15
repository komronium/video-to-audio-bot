from aiogram.utils.keyboard import InlineKeyboardBuilder

from config import settings
from utils.i18n import i18n

PRICES = settings.DIAMONDS_PRICES


def get_premium_hub_keyboard(lang: str, active_promo_label: str | None = None):
    """Top-level menu: three clear paths into the paid funnel.

    Layout (one button per row for mobile readability):
      💎 Buy Diamonds        — pay-as-you-go
      📅 Monthly Premium     — light commitment, recurring-feeling
      👑 Lifetime Premium    — best long-term value
      ⬅️ Back
    """
    builder = InlineKeyboardBuilder()
    builder.button(
        text=i18n.get_text("hub-diamonds-btn", lang),
        callback_data="diamond:list",
    )
    builder.button(
        text=i18n.get_text("hub-monthly-btn", lang).format(
            price=settings.MONTHLY_PREMIUM_PRICE
        ),
        callback_data="premium:monthly",
    )
    builder.button(
        text=i18n.get_text("hub-lifetime-btn", lang).format(
            price=settings.LIFETIME_PREMIUM_PRICE
        ),
        callback_data="premium:lifetime",
    )
    if active_promo_label:
        # Promo banner button is purely visual; clicking opens the hub again
        builder.button(text=f"🎁 {active_promo_label}", callback_data="diamond:hub")
    builder.button(text=i18n.get_text("back-button", lang), callback_data="diamond:back")
    builder.adjust(1)
    return builder.as_markup()


def get_prices_keyboard(lang: str):
    """Diamond pack list (legacy callable still used by external callers)."""
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
    builder.button(
        text=i18n.get_text("hub-back-btn", lang),
        callback_data="diamond:hub",
    )
    builder.adjust(1)
    return builder.as_markup()
