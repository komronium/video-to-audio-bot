import asyncio
import hashlib
import logging
import os
from datetime import datetime
from pathlib import Path

import redis
from aiogram import F, Router
from aiogram.exceptions import TelegramAPIError
from aiogram.types import FSInputFile, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy.ext.asyncio import AsyncSession

from config import settings
from services.user_service import UserService
from utils.i18n import i18n

INSTAGRAM_REGEX = r"https?://(www\.)?instagram\.com/(reel|p|tv)/[\w-]+"
TIKTOK_REGEX = r"https?://((www\.|vm\.|vt\.)?tiktok\.com|tiktok\.com)/[\w/@.?=&%-]+"

DAILY_LIMIT = 5
SOCIAL_SLOT_COST = 3
SOCIAL_DIAMOND_COST = 2
MAX_DURATION = 20 * 60  # 30 minutes

r = redis.Redis(host="localhost", port=6379, decode_responses=True)
router = Router()


def _get_buy_keyboard(lang: str):
    builder = InlineKeyboardBuilder()
    builder.button(text=i18n.get_text("buy-extra", lang), callback_data="diamond:list")
    builder.button(text=i18n.get_text("get-lifetime", lang), callback_data="diamond:lifetime")
    builder.adjust(1)
    return builder.as_markup()


def _social_info(url: str) -> dict:
    import yt_dlp
    with yt_dlp.YoutubeDL({"quiet": True, "no_warnings": True}) as ydl:
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
            tg.id, tg.username, tg.full_name,
            tg.language_code or "en", message.bot,
        )
    lang = user.lang or "en"
    is_lifetime = user.is_premium

    today = datetime.today().strftime("%Y-%m-%d")
    key = f"user:{user_id}:{today}"
    current = int(r.get(key) or 0)

    if not is_lifetime and current + SOCIAL_SLOT_COST > DAILY_LIMIT:
        if user.diamonds >= SOCIAL_DIAMOND_COST:
            for _ in range(SOCIAL_DIAMOND_COST):
                await user_service.use_diamond(user_id)
            await message.answer(
                f"💎 <b>{SOCIAL_DIAMOND_COST} diamonds used</b> — {platform.capitalize()} download activated."
            )
        else:
            ttl = r.ttl(key)
            time_str = ""
            if ttl and ttl > 0:
                h, m = ttl // 3600, (ttl % 3600) // 60
                time_str = f"\n⏳ <b>{'%dh %dm' % (h, m) if h else '%dm' % m}</b> remaining"
            await message.answer(
                i18n.get_text("social-limit", lang).format(
                    diamonds=user.diamonds or 0,
                    time=time_str,
                ),
                reply_markup=_get_buy_keyboard(lang),
            )
            return

    emoji = "📸" if platform == "instagram" else "🎵"
    processing_msg = await message.reply(f"{emoji} Downloading from {platform.capitalize()}...")
    file_path = None

    try:
        loop = asyncio.get_event_loop()
        name = f"{platform}_{hashlib.md5(url.encode()).hexdigest()[:10]}"

        info = await loop.run_in_executor(None, _social_info, url)
        duration = info.get("duration") or 0
        if duration > MAX_DURATION:
            await processing_msg.edit_text(
                f"⏱️ Video too long. Maximum is <b>{MAX_DURATION // 60} minutes</b>."
            )
            return

        await processing_msg.edit_text("🎧 Processing audio...")
        file_path = await loop.run_in_executor(None, _social_download, url, name)

        bot_me = await message.bot.get_me()
        await user_service.add_conversation(user_id, conv_type=platform)

        try:
            await processing_msg.delete()
        except (Exception,):
            pass

        await message.reply_document(
            FSInputFile(file_path),
            caption=i18n.get_text("converted-by", lang).format(bot_me.username),
        )

        if not r.exists(key):
            r.set(key, SOCIAL_SLOT_COST)
            r.expire(key, 86400)
        else:
            r.incrby(key, SOCIAL_SLOT_COST)

    except Exception as e:
        logging.exception(f"{platform} error for user {user_id}")
        err_str = str(e).lower()
        if "blocked" in err_str or "ip address" in err_str:
            user_msg = f"Your IP is blocked by {platform.capitalize()}. Try again later or use VPN."
        elif "not available" in err_str or "unavailable" in err_str:
            user_msg = f"This {platform.capitalize()} content is not available."
        elif "copyright" in err_str or "blocked in your country" in err_str:
            user_msg = f"Content blocked by copyright in your region."
        else:
            user_msg = "Please try again later."
        try:
            await processing_msg.edit_text(user_msg)
        except TelegramAPIError:
            pass
        try:
            await message.bot.send_message(
                settings.ADMIN_ID,
                f"<b>Video To Audio Bot | MP3: </b> {platform} error\n"
                f"<b>User:</b> <code>{user_id}</code>\n"
                f"<b>Error:</b> <code>{type(e).__name__}: {e}</code>",
            )
        except (Exception,):
            pass
    finally:
        if file_path and os.path.exists(file_path):
            os.remove(file_path)


@router.message(F.text.regexp(INSTAGRAM_REGEX))
async def instagram_handler(message: Message, db: AsyncSession):
    await _handle_social(message, db, message.text.strip(), "instagram")


@router.message(F.text.regexp(TIKTOK_REGEX))
async def tiktok_handler(message: Message, db: AsyncSession):
    await _handle_social(message, db, message.text.strip(), "tiktok")
