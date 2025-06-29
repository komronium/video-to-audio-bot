from aiogram import Router, F
from aiogram.types import CallbackQuery, LabeledPrice, PreCheckoutQuery
from aiogram.types.message import Message
from services.user_service import UserService

router = Router()

# --- Callback handler for buying diamonds via Telegram Stars ---
@router.callback_query(F.data == "buy_diamonds")
async def buy_diamonds_callback(call: CallbackQuery):
    # Diamondlar uchun Telegram Starlar soni:
    # 1 diamond = 5 ta Telegram Star
    prices = [
        LabeledPrice(label="1 Diamond 💎", amount=5),    # 5 star
        LabeledPrice(label="2 Diamonds 💎", amount=10),  # 10 star
        LabeledPrice(label="4 Diamonds 💎", amount=20),  # 20 star
        LabeledPrice(label="10 Diamonds 💎", amount=50), # 50 star
    ]
    await call.message.answer_invoice(
        title="Buy Diamonds 💎 via Telegram Stars",
        description=(
            "Each diamond gives you extra opportunities: unlimited conversations & large file conversions!\n\n"
            "You pay with Telegram Stars. 1 Diamond = 5 Telegram Stars."
        ),
        prices=prices,
        provider_token="",           # <-- o'zingizning tokeningiz
        payload="channel_support",
        currency="XTR",
        need_name=True,
        need_email=False,
    )
    await call.answer()

# --- Callback handler for buying Lifetime Premium ---
@router.callback_query(F.data == "lifetime-pay")
async def buy_lifetime_callback(call: CallbackQuery):
    prices = [
        LabeledPrice(label="💎 Lifetime Premium", amount=250),  # misol uchun 150 star
    ]
    await call.message.answer_invoice(
        title="Lifetime Premium 💎",
        description="Unlock unlimited uploads and conversions forever.",
        prices=prices,
        provider_token="",           # <-- o'zingizning tokeningiz
        payload="channel_support_lifetime",
        currency="XTR",
        need_name=True,
        need_email=False,
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