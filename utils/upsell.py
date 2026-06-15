from urllib.parse import quote_plus

from aiogram import Bot
from aiogram.utils.keyboard import InlineKeyboardBuilder

from services.user_service import UserService
from utils.daily_limit import DAILY_LIMIT, get_daily_count, reset_time_str
from utils.i18n import i18n

_bot_username: str | None = None


async def get_bot_username(bot: Bot) -> str:
    global _bot_username
    if _bot_username is None:
        _bot_username = (await bot.get_me()).username
    return _bot_username


async def result_keyboard(lang: str, user_id: int, user_service: UserService, bot: Bot):
    """A single 'share & earn' button shown under every delivered audio —
    the satisfaction-peak growth lever. Carries the user's referral link so
    invites that convert reward them."""
    code = await user_service.generate_referral_code(user_id)
    bot_username = await get_bot_username(bot)
    referral_link = f"https://t.me/{bot_username}?start={code}"
    share_text = i18n.get_text("referral-share-text", lang)
    share_url = (
        f"https://t.me/share/url?url={quote_plus(referral_link)}"
        f"&text={quote_plus(share_text)}"
    )
    builder = InlineKeyboardBuilder()
    builder.button(text=i18n.get_text("result-share-btn", lang), url=share_url)
    builder.adjust(1)
    return builder.as_markup()


async def get_buy_more_keyboard(lang: str, user_service: UserService, user_id: int, bot: Bot):
    """Limit-reached keyboard: invite-first (free for the user, growth-positive
    for the bot), then paid options."""
    code = await user_service.generate_referral_code(user_id)
    bot_username = await get_bot_username(bot)
    referral_link = f"https://t.me/{bot_username}?start={code}"
    share_text = i18n.get_text("referral-share-text", lang)
    share_url = f"https://t.me/share/url?url={quote_plus(referral_link)}&text={quote_plus(share_text)}"
    builder = InlineKeyboardBuilder()
    builder.button(text=i18n.get_text("invite-friend", lang), url=share_url)
    builder.button(text=i18n.get_text("buy-extra", lang), callback_data="diamond:list")
    builder.button(text=i18n.get_text("get-lifetime", lang), callback_data="diamond:lifetime")
    builder.adjust(1)
    return builder.as_markup()


async def post_conversion_upsell(
    bot: Bot,
    chat_id: int,
    user_id: int,
    lang: str,
    user_service: UserService,
    is_lifetime: bool,
):
    """Offer diamonds right after a successful conversion (satisfaction peak)."""
    if is_lifetime:
        return
    new_count = await get_daily_count(user_id)
    if new_count >= DAILY_LIMIT:
        await bot.send_message(
            chat_id,
            i18n.get_text("used-last-free", lang).format(time=reset_time_str()),
            reply_markup=await get_buy_more_keyboard(lang, user_service, user_id, bot),
        )
    elif new_count == DAILY_LIMIT - 1:
        builder = InlineKeyboardBuilder()
        builder.button(text=i18n.get_text("get-more-btn", lang), callback_data="diamond:list")
        builder.adjust(1)
        await bot.send_message(
            chat_id,
            i18n.get_text("one-free-left", lang),
            reply_markup=builder.as_markup(),
        )
