from aiogram import Router, F, Bot, types
from aiogram.filters import Command
from aiogram.types import CallbackQuery, LabeledPrice, PreCheckoutQuery
from aiogram.types.message import Message
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy.ext.asyncio import AsyncSession

from config import settings
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
async def buy_diamonds_callback(call: CallbackQuery, lang: str):
    await call.message.delete()
    await call.message.answer(
        i18n.get_text('buy-diamonds', lang),
        reply_markup=get_prices_keyboard(lang)
    )


# --- Callback handler for buying diamonds via Telegram Stars ---
@router.callback_query(F.data.startswith("buy-"))
async def buy_diamonds_callback(call: CallbackQuery, lang: str):
    diamonds_count = int(call.data.split('-')[1])
    prices = [
        LabeledPrice(label=i18n.get_text('diamond-count', lang).format(diamonds_count),
                     amount=diamonds_count * 5),
    ]
    await call.message.answer_invoice(
        title=i18n.get_text('buy-title', lang).format(diamonds_count),
        description=i18n.get_text('buy-desc', lang).format(diamonds_count, diamonds_count * 5),
        prices=prices,
        provider_token="",
        payload="channel_support",
        currency="XTR",
    )
    await call.answer()

# --- Callback handler for buying Lifetime Premium ---
@router.callback_query(F.data == "lifetime")
async def buy_lifetime_callback(call: CallbackQuery, lang: str):
    prices = [
        LabeledPrice(label=i18n.get_text('lifetime-title', lang), amount=250),  # misol uchun 150 star
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

    payload = message.successful_payment.invoice_payload
    amount = message.successful_payment.total_amount

    if payload == "channel_support":
        diamonds = 0
        if amount == 5:
            diamonds = 1
        elif amount == 10:
            diamonds = 2
        elif amount == 20:
            diamonds = 4
        elif amount == 50:
            diamonds = 10

        if diamonds > 0:
            await user_service.add_diamonds(user_id, diamonds)
            await message.answer(
                f"<b>💎 Congratulations!</b>\n{diamonds} diamonds added to your account.\n"
            )
            await bot.send_message(settings.GROUP_ID, f'<b>{amount} DIAMONDS</b> added.')
        else:
            await message.answer("❌ Payment received, but no diamonds were credited. Please contact support!")

    elif payload == "channel_support_lifetime":
        await user_service.set_lifetime(user_id)
        await bot.send_message(settings.GROUP_ID, '<b>250 DIAMONDS</b> added.')
        await message.answer("💎 Congratulations! You now have Lifetime Premium access.")

    else:
        await message.answer("<b>Unknown payment type.</b>\nPlease contact support: @TGBots_ContactBot")


@router.message(Command('diamonds'))
async def command_diamonds(message: types.Message, db: AsyncSession):
    user_service = UserService(db)
    user = await user_service.get_user(message.from_user.id)
    is_lifetime = await user_service.is_lifetime(user.id)

    if is_lifetime:
        await message.answer('<b>💎 Diamonds</b>\nYou have Lifetime Premium access! Enjoy unlimited features forever.')
    elif user.diamonds > 0:
        await message.answer(
            f"<b>💎 Diamonds</b>\nYou currently have <b>{user.diamonds}</b> diamond{'s' if user.diamonds > 1 else ''} in your account.\n"
            "Use diamonds to unlock extra conversations or features."
        )
    else:
        await message.answer(
            "<b>💎 Diamonds</b>\nYou have <b>0</b> diamonds in your account.\n\n"
            "Diamonds are required to unlock extra conversations and features.\n"
            "Buy more diamonds below:",
            reply_markup=get_buy_more_keyboard()
        )
