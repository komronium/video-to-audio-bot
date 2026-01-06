from aiogram import Bot, F, Router
from aiogram.types import CallbackQuery, LabeledPrice, PreCheckoutQuery, chat
from aiogram.types.message import Message
from sqlalchemy.ext.asyncio import AsyncSession

from config import settings
from database.session import get_db
from keyboards.prices import get_prices_keyboard
from services.user_service import UserService
from utils.i18n import i18n

router = Router()


@router.callback_query(F.data == "diamond:list")
async def buy_diamonds_callback(call: CallbackQuery):
    async with get_db() as db:
        service = UserService(db)
        lang = await service.get_lang(call.from_user.id)
        await call.message.edit_text(
            i18n.get_text("buy-diamonds", lang),
            reply_markup=get_prices_keyboard(lang),
        )


# --- Callback handler for buying diamonds via Telegram Stars ---
@router.callback_query(F.data.startswith("diamond:buy:"))
async def buy_any_diamonds_callback(call: CallbackQuery):
    async with get_db() as db:
        service = UserService(db)
        lang = await service.get_lang(call.from_user.id)
        diamonds_count = int(call.data.split(":")[2])
        amount = settings.DIAMONDS_PRICES[diamonds_count]

        prices = [
            LabeledPrice(
                label=i18n.get_text("diamond-count", lang).format(diamonds_count),
                amount=amount,
            ),
        ]
        await call.message.answer_invoice(
            title=i18n.get_text("buy-title", lang).format(diamonds_count),
            description=i18n.get_text("buy-desc", lang).format(diamonds_count, amount),
            prices=prices,
            provider_token="",
            payload="channel_support",
            currency="XTR",
        )
        await call.answer()


# --- Callback handler for buying Lifetime Premium ---
@router.callback_query(F.data == "diamond:lifetime")
async def buy_lifetime_callback(call: CallbackQuery):
    async with get_db() as db:
        service = UserService(db)
        lang = await service.get_lang(call.from_user.id)
        prices = [
            LabeledPrice(
                label=i18n.get_text("lifetime-title", lang),
                amount=settings.LIFETIME_PREMIUM_PRICE,
            ),
        ]
        await call.message.delete()
        await call.message.answer_invoice(
            title=i18n.get_text("lifetime-title", lang),
            description=i18n.get_text("lifetime-desc", lang),
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

    payload = message.successful_payment.invoice_payload
    amount = message.successful_payment.total_amount

    if payload == "channel_support":
        diamonds = list(settings.DIAMONDS_PRICES.keys())[
            list(settings.DIAMONDS_PRICES.values()).index(amount)
        ]

        if diamonds > 0:
            await user_service.add_diamonds(user_id, diamonds)
            await message.answer(i18n.get_text("congrats", lang).format(diamonds))
            user = message.from_user
            mention = f'<a href="tg://user?id={user.id}">{user.full_name}</a>'
            await bot.send_message(
                chat_id=settings.GROUP_ID,
                text=(
                    f"💎 <b>Diamonds Purchased</b>\n"
                    f"👤 {mention}\n"
                    f"✨ Diamonds: <b>{diamonds}</b>\n"
                    f"⭐️ Stars spent: <b>{amount}</b>"
                ),
                message_thread_id=17,
            )
        else:
            await message.answer(
                "❌ Payment received, but no diamonds were credited. Please contact support!"
            )

    elif payload == "channel_support_lifetime":
        await user_service.set_lifetime(user_id)
        user = message.from_user
        mention = f'<a href="tg://user?id={user.id}">{user.full_name}</a>'
        await bot.send_message(
            settings.GROUP_ID,
            (
                f"👑 <b>Lifetime Premium Activated</b>\n"
                f"👤 {mention}\n"
                f"⭐️ Stars spent: <b>{settings.LIFETIME_PREMIUM_PRICE}</b>"
            ),
        )
        await message.answer(i18n.get_text("congrats-lifetime", lang))

    else:
        await message.answer(
            "<b>Unknown payment type.</b>\nPlease contact support: @TGBots_ContactBot"
        )
