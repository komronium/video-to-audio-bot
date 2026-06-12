import asyncio
import hashlib
import logging
import os
from pathlib import Path

from aiogram import F, Router
from aiogram.exceptions import TelegramAPIError
from aiogram.types import FSInputFile, Message
from sqlalchemy.ext.asyncio import AsyncSession

from config import settings
from services.user_service import UserService
from utils.daily_limit import (
    DAILY_LIMIT,
    get_daily_count,
    increment_daily_count,
    seconds_until_midnight,
    ttl_to_str,
)
from utils.i18n import i18n
from utils.rewards import check_and_notify_rewards
from utils.upsell import get_bot_username, get_buy_more_keyboard, post_conversion_upsell

YOUTUBE_REGEX = r".*(youtu.*be.*)\/(watch\?v=|embed\/|v|shorts|)(.*?((?=[&#?])|$)).*"
INSTAGRAM_REGEX = r"https?://(www\.)?instagram\.com/(reel|p|tv)/[\w-]+"
TIKTOK_REGEX = r"https?://((www\.|vm\.|vt\.)?tiktok\.com|tiktok\.com)/[\w/@.?=&%-]+"

SOCIAL_SLOT_COST = 2
MAX_DURATION = 20 * 60

router = Router()


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

    current = await get_daily_count(user_id)
    charged = 0

    if not is_lifetime and current + SOCIAL_SLOT_COST > DAILY_LIMIT:
        # Atomic: charges all SOCIAL_SLOT_COST diamonds or none
        if await user_service.use_diamonds(user_id, SOCIAL_SLOT_COST):
            charged = SOCIAL_SLOT_COST
            await message.answer(
                i18n.get_text("social-diamonds-used", lang).format(
                    count=SOCIAL_SLOT_COST, platform=platform.capitalize()
                )
            )
        else:
            time_str = f"\n⏳ <b>{ttl_to_str(seconds_until_midnight())}</b>"
            await message.answer(
                i18n.get_text("social-limit", lang).format(
                    diamonds=user.diamonds or 0,
                    time=time_str,
                )
                + "\n\n"
                + i18n.get_text("limit-invite-tip", lang),
                reply_markup=await get_buy_more_keyboard(lang, user_service, user.user_id, message.bot),
            )
            return

    emoji = {"youtube": "▶️", "instagram": "📸", "tiktok": "🎵"}.get(platform, "🎬")
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
            await user_service.refund_diamonds(user_id, charged)
            await processing_msg.edit_text(
                i18n.get_text("social-too-long", lang).format(MAX_DURATION // 60)
            )
            return

        await processing_msg.edit_text(i18n.get_text("social-processing", lang))
        file_path = await loop.run_in_executor(None, _social_download, url, name)

        bot_username = await get_bot_username(message.bot)
        caption = i18n.get_text("converted-by", lang).format(bot_username)
        await user_service.add_conversation(user_id, conv_type=platform)

        try:
            await processing_msg.edit_text(i18n.get_text("uploading", lang))
            await message.bot.send_chat_action(message.chat.id, "upload_document")
        except TelegramAPIError:
            pass

        await message.reply_document(FSInputFile(file_path), caption=caption)
        await message.reply_voice(FSInputFile(file_path))

        try:
            await processing_msg.delete()
        except TelegramAPIError:
            pass

        await increment_daily_count(user_id, SOCIAL_SLOT_COST)
        await check_and_notify_rewards(message.bot, message.chat.id, user_id, user_service, lang)
        await post_conversion_upsell(
            message.bot, message.chat.id, user_id, lang, user_service, is_lifetime
        )

    except Exception as e:
        logging.exception(f"{platform} error for user {user_id}")
        await user_service.refund_diamonds(user_id, charged)
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
