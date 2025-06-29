from aiogram import Router, F
from aiogram.types import CallbackQuery, LabeledPrice, PreCheckoutQuery
from aiogram.types.message import Message
from aiogram.utils.keyboard import InlineKeyboardBuilder

from services.user_service import UserService

router = Router()


def get_prices_keyboard():
    builder = InlineKeyboardBuilder()
    builder.button(text="1 Diamond 💎", callback_data="buy-1")
    builder.button(text="2 Diamond 💎", callback_data="buy-2")
    builder.button(text="4 Diamond 💎", callback_data="buy-4")
    builder.button(text="10 Diamond 💎", callback_data="buy-10")
    builder.adjust(1)
    return builder.as_markup()


@router.callback_query(F.data == "buy_diamonds")
async def buy_diamonds_callback(call: CallbackQuery):
    await call.message.delete()
    await call.message.answer(
        "<b>Buy Diamonds 💎 via Telegram Stars</b>\n"
        "Each diamond gives you extra opportunities: unlimited conversations & large file conversions!\n\n"
        "You pay with Telegram Stars. 1 Diamond = 5 Telegram Stars.",
        reply_markup=get_prices_keyboard()
    )


# --- Callback handler for buying diamonds via Telegram Stars ---
@router.callback_query(F.data.startswith("buy-"))
async def buy_diamonds_callback(call: CallbackQuery):
    diamonds_count = int(call.data.split('-')[1])
    prices = [
        LabeledPrice(label=f"{diamonds_count} Diamond 💎", amount=diamonds_count * 5),
    ]
    await call.message.answer_invoice(
        title=f"Buy {diamonds_count} Diamond{'s' if diamonds_count > 1 else ''} 💎",
        description=(
            f"You are purchasing <b>{diamonds_count} Diamond{'s' if diamonds_count > 1 else ''}</b>.\n"
            f"Total: {diamonds_count * 5} Telegram Stars.\n\n"
            "Each diamond unlocks extra opportunities: unlimited conversations and large file conversions!\n"
            "Payment is made with Telegram Stars. 1 Diamond = 5 Telegram Stars."
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
    prices = [
        LabeledPrice(label="💎 Lifetime Premium", amount=250),  # misol uchun 150 star
    ]
    await call.message.delete()
    await call.message.answer_invoice(
        title="Lifetime Premium 💎",
        description="Unlock unlimited uploads and conversions forever.",
        prices=prices,
        provider_token="",
        payload="channel_support_lifetime",
        currency="XTR",
    )
    await call.answer()

# --- Successful Payment Handlers ---
@router.pre_checkout_query()
async def pre_checkout_handler(pre_checkout_q: PreCheckoutQuery):
    await pre_checkout_q.answer(ok=True)

@router.message(F.successful_payment)
async def successful_payment_handler(message: Message):
    user_id = message.from_user.id
    db = message.conf['db']  # yoki context orqali AsyncSession oling
    user_service = UserService(db)

    payload = message.successful_payment.invoice_payload
    amount = message.successful_payment.total_amount  # Bu yerda Telegram Starlar soni (XTR uchun)

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
                f"💎 Congratulations! {diamonds} diamonds added to your account.\n"
                f"(You spent {amount} Telegram Stars)"
            )
        else:
            await message.answer("❌ Payment received, but no diamonds were credited. Please contact support!")

    elif payload == "channel_support_lifetime":
        await user_service.set_lifetime(user_id)
        await message.answer("💎 Congratulations! You now have Lifetime Premium access.")

    else:
        await message.answer("Unknown payment type. Please contact support.")