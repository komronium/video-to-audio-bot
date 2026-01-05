import os
import re
import urllib.parse
from datetime import datetime
from pathlib import Path

import redis
import requests
from aiogram import F, Router
from aiogram.types import FSInputFile, Message
from requests.exceptions import MissingSchema
from sqlalchemy.ext.asyncio import AsyncSession

from config import settings
from services.converter import VideoConverter
from services.user_service import UserService
from utils.i18n import i18n

YOUTUBE_REGEX = r".*(youtu.*be.*)\/(watch\?v=|embed\/|v|shorts|)(.*?((?=[&#?])|$)).*"

MAX_FILE_SIZE = 100 * 1024 * 1024
DAILY_LIMIT = 10

r = redis.Redis(host="localhost", port=6379, decode_responses=True)

router = Router()


def extract_video_id(url: str) -> str:
    match = re.search(r"(?:v=|\/)([0-9A-Za-z_-]{11})", url)
    if match:
        return match.group(1)
    return None


@router.message(F.text.regexp(YOUTUBE_REGEX))
async def youtube_video_handler(message: Message, db: AsyncSession):
    video_url = message.text
    video_id = extract_video_id(video_url)

    if not video_id:
        await message.reply("Invalid YouTube URL.")
        return

    processing_msg = await message.reply("Downloading ...")

    audio_data = await VideoConverter().get_youtube_video(video_id)

    if audio_data["duration"] > 30 * 60:
        await message.reply("Video is too long. Max is 30 minutes")
        await processing_msg.delete()
        return

    link = audio_data.get("link")

    try:
        response = requests.get(link)
    except MissingSchema as e:
        return {"error": "Invalid URL", "link": link, "message": str(e)}

    content_disposition = response.headers.get("Content-Disposition")
    if content_disposition:
        filename = urllib.parse.unquote(
            content_disposition.split("filename=")[1].strip('"')
        )
        file_path = Path("videos") / filename
        with open(file_path, "wb") as f:
            f.write(response.content)
    else:
        raise RuntimeError("No filename in response headers")

    audio_data["file_path"] = str(file_path)

    user_id = message.from_user.id
    today = datetime.today().strftime("%Y-%m-%d")
    key = f"user:{user_id}:{today}"

    count = r.get(key)

    if count and int(count) >= DAILY_LIMIT:
        await message.reply(
            "❌ Daily limit reached!\nTo remove limits and get premium, click /premium"
        )
        return

    try:
        await processing_msg.edit_text("Converting ...")

        bot = await message.bot.get_me()
        user_service = UserService(db)
        lang = await user_service.get_lang(message.from_user.id)
        await user_service.add_conversation(message.from_user.id)
        await processing_msg.delete()
        await message.reply_document(
            FSInputFile(audio_data["file_path"]),
            caption=f"Converted by @{bot.username}",
        )

        await message.answer(i18n.get_text("promo-links", lang))

        if not r.exists(key):
            r.set(key, 1)
            r.expire(key, 86400)
        else:
            r.incr(key)
    except Exception as e:
        await message.answer("⚠️ Too many requests right now. Please try again later.")
        print(e)
    finally:
        if audio_data["file_path"] and os.path.exists(audio_data["file_path"]):
            os.remove(audio_data["file_path"])
