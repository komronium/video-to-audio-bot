from datetime import date

from aiogram import Bot, F, Router
from aiogram.exceptions import TelegramAPIError
from aiogram.filters import Command
from aiogram.types import CallbackQuery, LabeledPrice, Message, PreCheckoutQuery
from sqlalchemy.ext.asyncio import AsyncSession

from config import settings
from database.session import get_db
from keyboards.prices import get_premium_hub_keyboard, get_prices_keyboard
from services.promo import (
    apply_diamond_bonus,
    apply_price_discount,
    fmt_countdown,
    get_active_promo,
)
from services.user_service import UserService
from utils.i18n import i18n

router = Router()

# Reverse map: stars amount → diamonds count, computed once at import time
_STARS_TO_DIAMONDS: dict[int, int] = {v: k for k, v in settings.DIAMONDS_PRICES.items()}

# Payment payload tokens — kept short and stable so logs/dashboards stay readable
PAYLOAD_DIAMONDS = "channel_support"
PAYLOAD_LIFETIME = "channel_support_lifetime"
PAYLOAD_MONTHLY = "premium_monthly"


async def _hub_text(lang: str, user) -> str:
    """Compose the Premium Hub copy: status line + body + active promo
    countdown if any. One message, three actions — no scrolling needed."""
    promo = await get_active_promo()
    parts: list[str] = []

    # 1. Status line — what does the user currently have?
    if user and user.is_premium:
        parts.append(i18n.get_text("hub-status-lifetime", lang))
    elif user and user.is_active_premium:
        parts.append(
            i18n.get_text("hub-status-monthly", lang).format(
                until=user.subscription_until.strftime("%d %b %Y"),
            )
        )
    elif user:
        parts.append(
            i18n.get_text("hub-status-free", lang).format(
                diamonds=user.diamonds or 0,
            )
        )

    # 2. Body — value props for each tier
    parts.append(i18n.get_text("hub-body", lang).format(
        monthly_price=settings.MONTHLY_PREMIUM_PRICE,
        lifetime_price=settings.LIFETIME_PREMIUM_PRICE,
    ))

    # 3. Promo countdown banner
    if promo:
        parts.append(
            i18n.get_text("hub-promo-banner", lang).format(
                label=promo.label,
                countdown=fmt_countdown(promo.seconds_left()),
            )
        )

    return "\n\n".join(parts)


async def _show_hub(target, lang: str, user, *, edit: bool):
    promo = await get_active_promo()
    text = await _hub_text(lang, user)
    keyboard = get_premium_hub_keyboard(
        lang, active_promo_label=promo.label if promo else None
    )
    try:
        if edit:
            await target.edit_text(text, reply_markup=keyboard)
            return
    except TelegramAPIError:
        pass
    await target.answer(text, reply_markup=keyboard)


# ─── Entry points ──────────────────────────────────────────────────────────


@router.message(Command("diamonds"))
@router.message(Command("premium"))
@router.message(F.text.in_([i18n.get_text("diamonds-button", lang) for lang in i18n.LANGUAGES]))
async def diamonds_menu(message: Message):
    async with get_db() as db:
        service = UserService(db)
        lang = await service.get_lang(message.from_user.id)
        user = await service.get_user(message.from_user.id)
    await _show_hub(message, lang, user, edit=False)


@router.callback_query(F.data == "diamond:hub")
async def show_hub(call: CallbackQuery):
    async with get_db() as db:
        service = UserService(db)
        lang = await service.get_lang(call.from_user.id)
        user = await service.get_user(call.from_user.id)
    await _show_hub(call.message, lang, user, edit=True)
    await call.answer()


@router.callback_query(F.data == "diamond:back")
async def back_callback(call: CallbackQuery):
    try:
        await call.message.delete()
    except Exception:
        pass
    await call.answer()


# ─── Diamond packs ─────────────────────────────────────────────────────────


def _diamonds_list_text(lang: str, user, promo) -> str:
    text = i18n.get_text("buy-diamonds", lang)
    if promo and promo.type == "2x_diamonds":
        text = (
            i18n.get_text("hub-promo-banner", lang).format(
                label=promo.label, countdown=fmt_countdown(promo.seconds_left())
            )
            + "\n\n"
            + text
        )
    if user and not user.is_active_premium:
        text += "\n\n" + i18n.get_text("your-balance", lang).format(user.diamonds or 0)
    return text


@router.callback_query(F.data == "diamond:list")
async def buy_diamonds_callback(call: CallbackQuery):
    async with get_db() as db:
        service = UserService(db)
        lang = await service.get_lang(call.from_user.id)
        user = await service.get_user(call.from_user.id)
    promo = await get_active_promo()
    text = _diamonds_list_text(lang, user, promo)
    keyboard = get_prices_keyboard(lang)
    try:
        await call.message.edit_text(text, reply_markup=keyboard)
    except TelegramAPIError:
        await call.message.answer(text, reply_markup=keyboard)
    await call.answer()


@router.callback_query(F.data.startswith("diamond:buy:"))
async def buy_any_diamonds_callback(call: CallbackQuery):
    async with get_db() as db:
        lang = await UserService(db).get_lang(call.from_user.id)

    try:
        diamonds_count = int(call.data.split(":")[2])
    except (IndexError, ValueError):
        await call.answer()
        return

    amount = settings.DIAMONDS_PRICES.get(diamonds_count)
    if amount is None:
        await call.answer()
        return

    promo = await get_active_promo()
    final_diamonds, bonus = apply_diamond_bonus(diamonds_count, promo)
    extras: list[str] = []
    if bonus:
        extras.append(i18n.get_text("buy-promo-bonus", lang).format(bonus=bonus))
    if diamonds_count == 50:
        extras.append(i18n.get_text("save-30-line", lang))
    extra_text = ("\n\n" + "\n".join(extras)) if extras else ""

    # The Stars-paid amount is unchanged (2x_diamonds is a bonus, not a price
    # cut) — that way Telegram's pre-checkout doesn't reject mismatched totals.
    label_count = final_diamonds if bonus else diamonds_count
    await call.message.answer_invoice(
        title=i18n.get_text("buy-title", lang).format(label_count),
        description=(
            i18n.get_text("buy-desc", lang).format(label_count, amount) + extra_text
        ),
        prices=[LabeledPrice(
            label=i18n.get_text("diamond-count", lang).format(label_count),
            amount=amount,
        )],
        provider_token="",
        payload=PAYLOAD_DIAMONDS,
        currency="XTR",
    )
    await call.answer()


# ─── Lifetime premium ──────────────────────────────────────────────────────


@router.callback_query(F.data == "premium:lifetime")
@router.callback_query(F.data == "diamond:lifetime")  # legacy alias
async def buy_lifetime_callback(call: CallbackQuery):
    async with get_db() as db:
        lang = await UserService(db).get_lang(call.from_user.id)

    promo = await get_active_promo()
    final_price, original = apply_price_discount(
        settings.LIFETIME_PREMIUM_PRICE, promo, kind="lifetime"
    )
    desc = i18n.get_text("lifetime-desc", lang)
    if final_price != original:
        desc += "\n\n" + i18n.get_text("buy-promo-discount", lang).format(
            original=original, final=final_price
        )

    try:
        await call.message.delete()
    except Exception:
        pass

    await call.message.answer_invoice(
        title=i18n.get_text("lifetime-title", lang),
        description=desc,
        prices=[LabeledPrice(
            label=i18n.get_text("lifetime-title", lang), amount=final_price
        )],
        provider_token="",
        payload=PAYLOAD_LIFETIME,
        currency="XTR",
    )
    await call.answer()


# ─── Monthly premium ───────────────────────────────────────────────────────


@router.callback_query(F.data == "premium:monthly")
async def buy_monthly_callback(call: CallbackQuery):
    async with get_db() as db:
        lang = await UserService(db).get_lang(call.from_user.id)

    promo = await get_active_promo()
    final_price, original = apply_price_discount(
        settings.MONTHLY_PREMIUM_PRICE, promo, kind="monthly"
    )

    desc = i18n.get_text("monthly-desc", lang).format(days=settings.MONTHLY_PREMIUM_DAYS)
    if final_price != original:
        desc += "\n\n" + i18n.get_text("buy-promo-discount", lang).format(
            original=original, final=final_price
        )

    try:
        await call.message.delete()
    except Exception:
        pass

    await call.message.answer_invoice(
        title=i18n.get_text("monthly-title", lang),
        description=desc,
        prices=[LabeledPrice(
            label=i18n.get_text("monthly-title", lang), amount=final_price
        )],
        provider_token="",
        payload=PAYLOAD_MONTHLY,
        currency="XTR",
    )
    await call.answer()


# ─── Payment handlers ──────────────────────────────────────────────────────


@router.pre_checkout_query()
async def pre_checkout_handler(pre_checkout_q: PreCheckoutQuery):
    await pre_checkout_q.answer(ok=True)


@router.message(F.successful_payment)
async def successful_payment_handler(message: Message, db: AsyncSession, bot: Bot):
    user_id = message.from_user.id
    user_service = UserService(db)
    lang = await user_service.get_lang(user_id)

    payload = message.successful_payment.invoice_payload
    amount = message.successful_payment.total_amount
    tg_user = message.from_user
    mention = f'<a href="tg://user?id={tg_user.id}">{tg_user.full_name}</a>'

    if payload == PAYLOAD_DIAMONDS:
        await _on_diamonds_paid(message, bot, user_service, user_id, amount, lang, mention)
    elif payload == PAYLOAD_LIFETIME:
        await _on_lifetime_paid(message, bot, user_service, user_id, amount, lang, mention)
    elif payload == PAYLOAD_MONTHLY:
        await _on_monthly_paid(message, bot, user_service, user_id, amount, lang, mention)
    else:
        await message.answer(i18n.get_text("payment-issue", lang))


async def _on_diamonds_paid(message, bot, user_service, user_id, amount, lang, mention):
    base = _STARS_TO_DIAMONDS.get(amount)
    if not base:
        await message.answer(i18n.get_text("payment-issue", lang))
        return
    promo = await get_active_promo()
    final_diamonds, bonus = apply_diamond_bonus(base, promo)
    await user_service.add_diamonds(user_id, final_diamonds)
    if bonus:
        await message.answer(
            i18n.get_text("congrats-with-bonus", lang).format(
                total=final_diamonds, bonus=bonus
            )
        )
    else:
        await message.answer(i18n.get_text("congrats", lang).format(final_diamonds))
    try:
        await bot.send_message(
            chat_id=settings.GROUP_ID,
            text=(
                f"💎 <b>Diamonds Purchased</b>\n"
                f"👤 {mention}\n"
                f"✨ Diamonds: <b>{final_diamonds}</b>"
                + (f" (incl. +{bonus} promo)" if bonus else "")
                + f"\n⭐️ Stars spent: <b>{amount}</b>"
            ),
            message_thread_id=17,
        )
    except TelegramAPIError:
        pass


async def _on_lifetime_paid(message, bot, user_service, user_id, amount, lang, mention):
    await user_service.set_lifetime(user_id)
    await message.answer(i18n.get_text("congrats-lifetime", lang))
    try:
        await bot.send_message(
            settings.GROUP_ID,
            f"👑 <b>Lifetime Premium Activated</b>\n"
            f"👤 {mention}\n"
            f"⭐️ Stars spent: <b>{amount}</b>",
        )
    except TelegramAPIError:
        pass


async def _on_monthly_paid(message, bot, user_service, user_id, amount, lang, mention):
    new_until = await user_service.extend_subscription(
        user_id, days=settings.MONTHLY_PREMIUM_DAYS
    )
    if not new_until:
        await message.answer(i18n.get_text("payment-issue", lang))
        return
    await message.answer(
        i18n.get_text("congrats-monthly", lang).format(
            until=new_until.strftime("%d %b %Y"),
        )
    )
    try:
        await bot.send_message(
            settings.GROUP_ID,
            f"📅 <b>Monthly Premium</b>\n"
            f"👤 {mention}\n"
            f"📆 Until: <b>{new_until.strftime('%d %b %Y')}</b>\n"
            f"⭐️ Stars spent: <b>{amount}</b>",
        )
    except TelegramAPIError:
        pass
