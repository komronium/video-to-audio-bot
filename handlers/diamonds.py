from aiogram import Router, F, Bot, types
from aiogram.types import CallbackQuery, LabeledPrice, PreCheckoutQuery
from aiogram.types.message import Message
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy.ext.asyncio import AsyncSession

from config import settings
from database.session import get_db
from handlers.video import get_buy_more_keyboard
from services.user_service import UserService
from utils.i18n import i18n

router = Router()


def get_prices_keyboard(lang: str):
    builder = InlineKeyboardBuilder()
    builder.button(text=i18n.get_text('1-diamond', lang), callback_data="buy-1")
    builder.button(text=i18n.get_text('2-diamond', lang), callback_data="buy-2")
    builder.button(text=i18n.get_text('4-diamond', lang), callback_data="buy-4")
    builder.button(text=i18n.get_text('10-diamond', lang), callback_data="buy-10")
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
        prices = [
            LabeledPrice(label=i18n.get_text('diamond-count', lang).format(diamonds_count),
                         amount=diamonds_count * settings.DIAMONDS_PRICE),
        ]
        await call.message.answer_invoice(
            title=i18n.get_text('buy-title', lang).format(diamonds_count),
            description=i18n.get_text('buy-desc', lang).format(
                diamonds_count,
                diamonds_count * settings.DIAMONDS_PRICE
            ),
            prices=prices,
            provider_token="",
            payload="channel_support",
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

    payload = message.successful_payment.invoice_payload
    amount = message.successful_payment.total_amount

    if payload == "channel_support":
        diamonds = amount * settings.DIAMONDS_PRICE

        if diamonds > 0:
            await user_service.add_diamonds(user_id, diamonds)
            await message.answer(
                i18n.get_text('congrats', lang).format(diamonds)
            )
            await bot.send_message(settings.GROUP_ID, f'<b>{amount} DIAMONDS</b> added.')
        else:
            await message.answer("❌ Payment received, but no diamonds were credited. Please contact support!")

    elif payload == "channel_support_lifetime":
        await user_service.set_lifetime(user_id)
        await bot.send_message(settings.GROUP_ID, f'<b>{settings.LIFETIME_PREMIUM_PRICE} STARS</b> added.')
        await message.answer(i18n.get_text('congrats-lifetime', lang))

    else:
        await message.answer("<b>Unknown payment type.</b>\nPlease contact support: @TGBots_ContactBot")
