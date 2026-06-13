from aiogram import Bot, F, Router
from aiogram.exceptions import TelegramAPIError
from aiogram.filters import Command
from aiogram.types import CallbackQuery, LabeledPrice, PreCheckoutQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from config import settings
from database.session import get_db
from keyboards.prices import get_prices_keyboard
from services.user_service import UserService
from utils.i18n import i18n

router = Router()

# Reverse map: stars → diamonds count, built once at import time
_STARS_TO_DIAMONDS: dict[int, int] = {v: k for k, v in settings.DIAMONDS_PRICES.items()}


def _diamonds_text(lang: str, user) -> str:
    text = i18n.get_text("buy-diamonds", lang)
    if user and not user.is_premium:
        text += "\n\n" + i18n.get_text("your-balance", lang).format(user.diamonds or 0)
    return text


@router.message(Command("diamonds"))
@router.message(F.text.in_([i18n.get_text("diamonds-button", lang) for lang in i18n.LANGUAGES]))
async def diamonds_menu(message: Message):
    async with get_db() as db:
        service = UserService(db)
        lang = await service.get_lang(message.from_user.id)
        user = await service.get_user(message.from_user.id)
    await message.answer(_diamonds_text(lang, user), reply_markup=get_prices_keyboard(lang))


@router.callback_query(F.data == "diamond:back")
async def back_callback(call: CallbackQuery):
    # Close the price list (the reply-keyboard menu stays available below)
    try:
        await call.message.delete()
    except Exception:
        pass
    await call.answer()


@router.callback_query(F.data == "diamond:list")
async def buy_diamonds_callback(call: CallbackQuery):
    async with get_db() as db:
        service = UserService(db)
        lang = await service.get_lang(call.from_user.id)
        user = await service.get_user(call.from_user.id)
    try:
        await call.message.edit_text(
            _diamonds_text(lang, user),
            reply_markup=get_prices_keyboard(lang),
        )
    except TelegramAPIError:
        await call.message.answer(
            _diamonds_text(lang, user),
            reply_markup=get_prices_keyboard(lang),
        )
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

    extra_offer = f"\n\n{i18n.get_text('save-30-line', lang)}" if diamonds_count == 50 else ""

    await call.message.answer_invoice(
        title=i18n.get_text("buy-title", lang).format(diamonds_count),
        description=i18n.get_text("buy-desc", lang).format(diamonds_count, amount) + extra_offer,
        prices=[LabeledPrice(label=i18n.get_text("diamond-count", lang).format(diamonds_count), amount=amount)],
        provider_token="",
        payload="channel_support",
        currency="XTR",
    )
    await call.answer()


@router.callback_query(F.data == "diamond:lifetime")
async def buy_lifetime_callback(call: CallbackQuery):
    async with get_db() as db:
        lang = await UserService(db).get_lang(call.from_user.id)

    try:
        await call.message.delete()
    except Exception:
        pass

    await call.message.answer_invoice(
        title=i18n.get_text("lifetime-title", lang),
        description=i18n.get_text("lifetime-desc", lang),
        prices=[LabeledPrice(label=i18n.get_text("lifetime-title", lang), amount=settings.LIFETIME_PREMIUM_PRICE)],
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
    lang = await user_service.get_lang(user_id)

    payload = message.successful_payment.invoice_payload
    amount = message.successful_payment.total_amount
    tg_user = message.from_user
    mention = f'<a href="tg://user?id={tg_user.id}">{tg_user.full_name}</a>'

    if payload == "channel_support":
        diamonds = _STARS_TO_DIAMONDS.get(amount)
        if diamonds:
            await user_service.add_diamonds(user_id, diamonds)
            await message.answer(i18n.get_text("congrats", lang).format(diamonds))
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
            await message.answer(i18n.get_text("payment-issue", lang))

    elif payload == "channel_support_lifetime":
        await user_service.set_lifetime(user_id)
        await bot.send_message(
            settings.GROUP_ID,
            f"👑 <b>Lifetime Premium Activated</b>\n"
            f"👤 {mention}\n"
            f"⭐️ Stars spent: <b>{settings.LIFETIME_PREMIUM_PRICE}</b>",
        )
        await message.answer(i18n.get_text("congrats-lifetime", lang))

    else:
        await message.answer(i18n.get_text("payment-issue", lang))
