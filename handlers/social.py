import asyncio
import hashlib
import logging
import os
from datetime import datetime
from pathlib import Path
from urllib.parse import quote_plus

import redis.asyncio as aioredis
from aiogram import F, Router
from aiogram.exceptions import TelegramAPIError
from aiogram.types import FSInputFile, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy.ext.asyncio import AsyncSession

from config import settings
from services.user_service import UserService
from utils.i18n import i18n
from utils.rewards import check_and_notify_rewards

YOUTUBE_REGEX = r".*(youtu.*be.*)\/(watch\?v=|embed\/|v|shorts|)(.*?((?=[&#?])|$)).*"
INSTAGRAM_REGEX = r"https?://(www\.)?instagram\.com/(reel|p|tv)/[\w-]+"
TIKTOK_REGEX = r"https?://((www\.|vm\.|vt\.)?tiktok\.com|tiktok\.com)/[\w/@.?=&%-]+"

DAILY_LIMIT = 3
SOCIAL_SLOT_COST = 2
MAX_DURATION = 20 * 60

_redis = aioredis.Redis(host="localhost", port=6379, decode_responses=True)
_bot_username: str | None = None

router = Router()


async def _get_bot_username(bot) -> str:
    global _bot_username
    if _bot_username is None:
        _bot_username = (await bot.get_me()).username
    return _bot_username


async def _get_buy_keyboard(lang: str, user_service: UserService, user_id: int, bot):
    builder = InlineKeyboardBuilder()
    builder.button(text=i18n.get_text("buy-extra", lang), callback_data="diamond:list")
    builder.button(text=i18n.get_text("get-lifetime", lang), callback_data="diamond:lifetime")
    code = await user_service.generate_referral_code(user_id)
    bot_username = await _get_bot_username(bot)
    referral_link = f"https://t.me/{bot_username}?start={code}"
    share_text = i18n.get_text("referral-share-text", lang)
    share_url = f"https://t.me/share/url?url={quote_plus(referral_link)}&text={quote_plus(share_text)}"
    builder.button(text=i18n.get_text("invite-friend", lang), url=share_url)
    builder.adjust(1)
    return builder.as_markup()


async def _get_daily_count(user_id: int) -> int:
    today = datetime.today().strftime("%Y-%m-%d")
    return int(await _redis.get(f"user:{user_id}:{today}") or 0)


async def _get_daily_ttl(user_id: int) -> int:
    today = datetime.today().strftime("%Y-%m-%d")
    return await _redis.ttl(f"user:{user_id}:{today}")


def _ttl_to_str(ttl: int) -> str:
    if ttl <= 0:
        return "soon"
    h, m = ttl // 3600, (ttl % 3600) // 60
    return f"{h}h {m}m" if h else f"{m}m"


def _social_info(url: str) -> dict:
    import yt_dlp
    opts = {"quiet": True, "no_warnings": True, "cookiefile": "cookies.txt"}
    with yt_dlp.YoutubeDL(opts) as ydl:
        return ydl.extract_info(url, download=False)


def _social_download(url: str, name: str) -> str:
    import yt_dlp
    Path("audios").mkdir(exist_ok=True)
    output = f"audios/{name}"
    opts = {
        "format": "bestaudio/best",
        "outtmpl": f"{output}.%(ext)s",
        "postprocessors": [{"key": "FFmpegExtractAudio", "preferredcodec": "mp3"}],
        "quiet": True,
        "no_warnings": True,
        "cookiefile": "cookies.txt",
    }
    with yt_dlp.YoutubeDL(opts) as ydl:
        ydl.download([url])
    return f"{output}.mp3"


async def _handle_social(message: Message, db: AsyncSession, url: str, platform: str):
    user_id = message.from_user.id
    user_service = UserService(db)

    user = await user_service.get_user(user_id)
    if not user:
        tg = message.from_user
        user = await user_service.add_user(
            tg.id, tg.username, tg.full_name, tg.language_code or "en", message.bot
        )
    lang = user.lang or "en"
    is_lifetime = user.is_premium

    current = await _get_daily_count(user_id)

    if not is_lifetime and current + SOCIAL_SLOT_COST > DAILY_LIMIT:
        if user.diamonds >= SOCIAL_SLOT_COST:
            for _ in range(SOCIAL_SLOT_COST):
                await user_service.use_diamond(user_id)
            await message.answer(
                i18n.get_text("social-diamonds-used", lang).format(
                    count=SOCIAL_SLOT_COST, platform=platform.capitalize()
                )
            )
        else:
            ttl = await _get_daily_ttl(user_id)
            time_str = f"\n⏳ <b>{_ttl_to_str(ttl)}</b>" if ttl > 0 else ""
            await message.answer(
                i18n.get_text("social-limit", lang).format(
                    diamonds=user.diamonds or 0,
                    time=time_str,
                )
                + "\n\n"
                + i18n.get_text("limit-invite-tip", lang),
                reply_markup=await _get_buy_keyboard(lang, user_service, user.user_id, message.bot),
            )
            return

    emoji = "📸" if platform == "instagram" else "🎵"
    processing_msg = await message.reply(
        i18n.get_text("social-downloading", lang).format(
            emoji=emoji, platform=platform.capitalize()
        )
    )
    file_path = None

    try:
        loop = asyncio.get_running_loop()
        name = f"{platform}_{hashlib.md5(url.encode()).hexdigest()[:10]}"

        info = await loop.run_in_executor(None, _social_info, url)
        duration = info.get("duration") or 0
        if duration > MAX_DURATION:
            await processing_msg.edit_text(
                i18n.get_text("social-too-long", lang).format(MAX_DURATION // 60)
            )
            return

        await processing_msg.edit_text(i18n.get_text("social-processing", lang))
        file_path = await loop.run_in_executor(None, _social_download, url, name)

        bot_username = await _get_bot_username(message.bot)
        caption = i18n.get_text("converted-by", lang).format(bot_username)
        await user_service.add_conversation(user_id, conv_type=platform)

        try:
            await processing_msg.delete()
        except TelegramAPIError:
            pass

        await message.reply_document(FSInputFile(file_path), caption=caption)
        await message.reply_voice(FSInputFile(file_path))

        today = datetime.today().strftime("%Y-%m-%d")
        key = f"user:{user_id}:{today}"
        if not await _redis.exists(key):
            await _redis.set(key, SOCIAL_SLOT_COST)
            await _redis.expire(key, 86400)
        else:
            await _redis.incrby(key, SOCIAL_SLOT_COST)

        await check_and_notify_rewards(message, user_id, user_service, lang)

        # Post-conversion upsell for free users
        if not is_lifetime:
            new_count = await _get_daily_count(user_id)
            if new_count >= DAILY_LIMIT:
                ttl = await _get_daily_ttl(user_id)
                await message.answer(
                    i18n.get_text("used-last-free", lang).format(time=_ttl_to_str(ttl)),
                    reply_markup=await _get_buy_keyboard(lang, user_service, user_id, message.bot),
                )

    except Exception as e:
        logging.exception(f"{platform} error for user {user_id}")
        err_str = str(e).lower()
        if "blocked" in err_str or "ip address" in err_str:
            user_msg = i18n.get_text("social-error-blocked", lang).format(platform.capitalize())
        elif "not available" in err_str or "unavailable" in err_str:
            user_msg = i18n.get_text("social-error-unavailable", lang).format(platform.capitalize())
        elif "copyright" in err_str or "blocked in your country" in err_str:
            user_msg = i18n.get_text("social-error-copyright", lang)
        else:
            user_msg = i18n.get_text("error-server", lang)
        try:
            await processing_msg.edit_text(user_msg)
        except TelegramAPIError:
            pass
        try:
            await message.bot.send_message(
                settings.ADMIN_ID,
                f"<b>❌ {platform} error</b>\n"
                f"<b>User:</b> <code>{user_id}</code>\n"
                f"<b>Error:</b> <code>{type(e).__name__}: {e}</code>",
            )
        except TelegramAPIError:
            pass
    finally:
        if file_path and os.path.exists(file_path):
            os.remove(file_path)


@router.message(F.text.regexp(YOUTUBE_REGEX))
async def youtube_handler(message: Message, db: AsyncSession):
    await _handle_social(message, db, message.text.strip(), "youtube")


@router.message(F.text.regexp(INSTAGRAM_REGEX))
async def instagram_handler(message: Message, db: AsyncSession):
    await _handle_social(message, db, message.text.strip(), "instagram")


@router.message(F.text.regexp(TIKTOK_REGEX))
async def tiktok_handler(message: Message, db: AsyncSession):
    await _handle_social(message, db, message.text.strip(), "tiktok")
