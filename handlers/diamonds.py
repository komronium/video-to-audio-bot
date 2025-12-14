from aiogram import Router, F, Bot
from aiogram.types import CallbackQuery, LabeledPrice, PreCheckoutQuery
from aiogram.types.message import Message
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy.ext.asyncio import AsyncSession
from html import escape

from config import settings
from database.session import get_db
from services.user_service import UserService
from utils.i18n import i18n

router = Router()


def get_prices_keyboard(lang: str):
    builder = InlineKeyboardBuilder()
    # Tiered packs and their star prices
    packs = [1, 5, 10, 25]
    pack_prices = {1: 2, 5: 8, 10: 15, 25: 30}
    for p in packs:
        label = i18n.get_text('diamond-count', lang).format(p)
        label = f"{label} — {pack_prices[p]} ⭐"
        builder.button(text=label, callback_data=f"buy-{p}")
    builder.adjust(1)
    return builder.as_markup()


@router.callback_query(F.data == "buy_diamonds")
async def buy_diamonds_callback(call: CallbackQuery):
    async with get_db() as db:
        service = UserService(db)
        lang = await service.get_lang(call.from_user.id)
        await call.message.delete()
        await call.message.answer(
            i18n.get_text('buy-diamonds', lang).format(settings.DIAMONDS_PRICE),
            reply_markup=get_prices_keyboard(lang)
        )


# --- Callback handler for buying diamonds via Telegram Stars ---
@router.callback_query(F.data.startswith("buy-"))
async def buy_diamonds_callback(call: CallbackQuery):
    async with get_db() as db:
        service = UserService(db)
        lang = await service.get_lang(call.from_user.id)
        diamonds_count = int(call.data.split('-')[1])
        # pricing map (stars per pack)
        pack_prices = {1: 2, 5: 8, 10: 15, 25: 30}
        price = pack_prices.get(diamonds_count, diamonds_count * settings.DIAMONDS_PRICE)
        prices = [
            LabeledPrice(label=i18n.get_text('diamond-count', lang).format(diamonds_count) + f" ({price} ⭐)",
                         amount=price),
        ]
        payload = f"channel_support:{diamonds_count}"
        await call.message.answer_invoice(
            title=i18n.get_text('buy-title', lang).format(diamonds_count),
            description=i18n.get_text('buy-desc', lang).format(
                diamonds_count,
                price
            ),
            prices=prices,
            provider_token="",
            payload=payload,
            currency="XTR",
        )
        await call.answer()

# --- Callback handler for buying Lifetime Premium ---
@router.callback_query(F.data == "lifetime")
async def buy_lifetime_callback(call: CallbackQuery):
    async with get_db() as db:
        service = UserService(db)
        lang = await service.get_lang(call.from_user.id)
        prices = [
            LabeledPrice(label=i18n.get_text('lifetime-title', lang), amount=settings.LIFETIME_PREMIUM_PRICE),
        ]
        await call.message.delete()
        await call.message.answer_invoice(
            title=i18n.get_text('lifetime-title', lang),
            description=i18n.get_text('lifetime-desc', lang),
            prices=prices,
            provider_token="",
            payload="channel_support_lifetime",
            currency="XTR",
        )
        await call.answer()


@router.pre_checkout_query()
async def pre_checkout_handler(pre_checkout_q: PreCheckoutQuery):
    await pre_checkout_q.answer(ok=True)


@router.message(F.successful_payment)
async def successful_payment_handler(message: Message, db: AsyncSession, bot: Bot):
    user_id = message.from_user.id
    user_service = UserService(db)
    lang = await user_service.get_lang(message.from_user.id)
    user = await user_service.get_user(user_id)

    payload = message.successful_payment.invoice_payload
    amount = message.successful_payment.total_amount

    if payload and payload.startswith("channel_support"):
        # payload format: channel_support:<diamonds_count>
        parts = payload.split(":")
        diamonds = 0
        try:
            diamonds = int(parts[1]) if len(parts) > 1 else 0
        except Exception:
            diamonds = 0

        # pricing map (stars per pack)
        pack_prices = {1: 2, 5: 8, 10: 15, 25: 30}
        spent = pack_prices.get(diamonds, diamonds * settings.DIAMONDS_PRICE)

        if diamonds > 0:
            await user_service.add_diamonds(user_id, diamonds)
            new_balance = await user_service.get_user_diamonds(user_id)
            await message.answer(
                i18n.get_text('congrats', lang).format(diamonds)
            )
            display_name = escape(
                (user.name if user and user.name else message.from_user.full_name) or "User"
            )
            mention = f'<a href="tg://user?id={user_id}">{display_name}</a>'
            await bot.send_message(
                chat_id=settings.GROUP_ID,
                message_thread_id=settings.DIAMONDS_TOPIC_ID,
                text=(
                    "💎 <b>DIAMOND DROP!</b>\n"
                    f"👤 {mention}\n"
                    f"✨ Purchased: <b>{diamonds}</b> diamonds\n"
                    f"⭐ Stars spent: <b>{spent}</b>\n"
                    f"💠 New balance: <b>{new_balance}</b>"
                ),
                parse_mode='HTML'
            )
        else:
            await message.answer("❌ Payment received, but no diamonds were credited. Please contact support!")

    elif payload == "channel_support_lifetime":
        await user_service.set_lifetime(user_id)
        display_name = escape(
            (user.name if user and user.name else message.from_user.full_name) or "User"
        )
        mention = f'<a href="tg://user?id={user_id}">{display_name}</a>'
        await bot.send_message(
            settings.GROUP_ID,
            (
                "👑 <b>LIFETIME PREMIUM UNLOCKED!</b>\n"
                f"👤 {mention}\n"
                f"⭐️ Stars spent: <b>{settings.LIFETIME_PREMIUM_PRICE}</b>"
            )
        )
        await message.answer(i18n.get_text('congrats-lifetime', lang))

    else:
        await message.answer("<b>Unknown payment type.</b>\nPlease contact support: @TGBots_ContactBot")
