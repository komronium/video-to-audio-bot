import asyncio
import logging
import os
import re
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

YOUTUBE_REGEX = r".*(youtu.*be.*)\/(watch\?v=|embed\/|v|shorts|)(.*?((?=[&#?])|$)).*"
DAILY_LIMIT = 5
YT_SLOT_COST = 2        # YouTube uses 2 daily slots
YT_DIAMOND_COST = 2     # YouTube costs 2 diamonds
MAX_DURATION = 30 * 60  # seconds

r = redis.Redis(host="localhost", port=6379, decode_responses=True)
router = Router()


def extract_video_id(url: str) -> str:
    match = re.search(r"(?:v=|\/)([0-9A-Za-z_-]{11})", url)
    return match.group(1) if match else None


def _get_buy_keyboard(lang: str):
    builder = InlineKeyboardBuilder()
    builder.button(text=i18n.get_text("buy-extra", lang), callback_data="diamond:list")
    builder.button(text=i18n.get_text("get-lifetime", lang), callback_data="diamond:lifetime")
    builder.adjust(1)
    return builder.as_markup()


def _yt_info(video_id: str) -> dict:
    """Fetch metadata only (no download) — blocking, run in executor."""
    import yt_dlp
    with yt_dlp.YoutubeDL({"quiet": True, "no_warnings": True}) as ydl:
        return ydl.extract_info(
            f"https://www.youtube.com/watch?v={video_id}",
            download=False,
        )


def _yt_download(video_id: str) -> str:
    """Download and convert to mp3 — blocking, run in executor."""
    import yt_dlp
    Path("audios").mkdir(exist_ok=True)
    output = f"audios/yt_{video_id}"
    opts = {
        "format": "bestaudio/best",
        "outtmpl": f"{output}.%(ext)s",
        "postprocessors": [{"key": "FFmpegExtractAudio", "preferredcodec": "mp3"}],
        "quiet": True,
        "no_warnings": True,
    }
    with yt_dlp.YoutubeDL(opts) as ydl:
        ydl.download([f"https://www.youtube.com/watch?v={video_id}"])
    return f"{output}.mp3"


@router.message(F.text.regexp(YOUTUBE_REGEX))
async def youtube_handler(message: Message, db: AsyncSession):
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

    video_id = extract_video_id(message.text)
    if not video_id:
        await message.reply("❌ Invalid YouTube link.")
        return

    # ── Daily limit check (before any download) ──────────
    today = datetime.today().strftime("%Y-%m-%d")
    key = f"user:{user_id}:{today}"
    current = int(r.get(key) or 0)

    if not is_lifetime and current + YT_SLOT_COST > DAILY_LIMIT:
        if user.diamonds >= YT_DIAMOND_COST:
            for _ in range(YT_DIAMOND_COST):
                await user_service.use_diamond(user_id)
            await message.answer(
                f"💎 <b>{YT_DIAMOND_COST} diamonds used</b> — YouTube download activated."
            )
        else:
            ttl = r.ttl(key)
            time_str = ""
            if ttl and ttl > 0:
                h, m = ttl // 3600, (ttl % 3600) // 60
                time_str = f"\n⏳ <b>{'%dh %dm' % (h, m) if h else '%dm' % m}</b> remaining"
            await message.answer(
                f"⛔ <b>Daily limit reached</b>\n\n"
                f"YouTube downloads cost <b>{YT_SLOT_COST}</b> conversions each.{time_str}",
                reply_markup=_get_buy_keyboard(lang),
            )
            return

    # ── Fetch metadata (duration check before download) ──
    processing_msg = await message.reply("⬇️ Downloading from YouTube...")
    file_path = None

    try:
        loop = asyncio.get_event_loop()

        info = await loop.run_in_executor(None, _yt_info, video_id)
        if info.get("duration", 0) > MAX_DURATION:
            await processing_msg.edit_text("⏱️ Video too long. Maximum is <b>30 minutes</b>.")
            return

        await processing_msg.edit_text("🎧 Processing audio...")
        file_path = await loop.run_in_executor(None, _yt_download, video_id)

        bot_me = await message.bot.get_me()
        await user_service.add_conversation(user_id)

        try:
            await processing_msg.delete()
        except (Exception,):
            pass

        await message.reply_document(
            FSInputFile(file_path),
            caption=i18n.get_text("converted-by", lang).format(bot_me.username),
        )

        # Increment counter by YT_SLOT_COST
        if not r.exists(key):
            r.set(key, YT_SLOT_COST)
            r.expire(key, 86400)
        else:
            r.incrby(key, YT_SLOT_COST)

        await message.answer(i18n.get_text("promo-links", lang))

    except Exception as e:
        logging.exception(f"YouTube error for user {user_id}")
        try:
            await processing_msg.edit_text("⚠️ Failed to download. Please try again later.")
        except TelegramAPIError:
            pass
        try:
            await message.bot.send_message(
                settings.ADMIN_ID,
                f"<b>❌ YouTube error</b>\n"
                f"<b>User:</b> <code>{user_id}</code>\n"
                f"<b>Error:</b> <code>{type(e).__name__}: {e}</code>",
            )
        except Exception:
            pass
    finally:
        if file_path and os.path.exists(file_path):
            os.remove(file_path)
