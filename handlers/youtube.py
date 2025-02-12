
import os
import re
import redis
from pathlib import Path
from yt_dlp import YoutubeDL
from datetime import datetime
from aiogram import Router, F
from aiogram.types import Message, FSInputFile, Document
from sqlalchemy.ext.asyncio import AsyncSession

from services.converter import convert_video_to_audio, get_youtube_video
from services.user_service import UserService

YOUTUBE_REGEX = r'.*(youtu.*be.*)\/(watch\?v=|embed\/|v|shorts|)(.*?((?=[&#?])|$)).*'

MAX_FILE_SIZE = 100 * 1024 * 1024
DAILY_LIMIT = 10

r = redis.Redis(host='localhost', port=6379, decode_responses=True)

router = Router()


@router.message(F.text.regexp(YOUTUBE_REGEX))
async def youtube_video_handler(message: Message, db: AsyncSession):
    video_url = message.text

    with YoutubeDL({'format': 'bestaudio/best', 'quiet': True, 'cookiefile': 'cookies.txt'}) as ydl:
        info = ydl.extract_info(video_url, download=False)
        duration = info.get('duration')

    if duration > 30 * 60:
        await message.reply('Video is too long. Max is 30 minutes')
        return

    processing_msg = await message.reply("Downloading ...")

    video_path, filename = get_youtube_video(video_url)

    user_id = message.from_user.id
    today = datetime.today().strftime('%Y-%m-%d')
    key = f'user:{user_id}:{today}'

    count = r.get(key)

    if count and int(count) >= DAILY_LIMIT:
        await message.reply(
            "❌ Daily limit reached!\n"
            "To remove limits and get premium, click /premium"
        )
        return

    audio_path = None

    try:
        await processing_msg.edit_text("Converting ...")

        audio_path = convert_video_to_audio(video_path, f'audios/{filename}')
        audio_file = FSInputFile(path=audio_path)

        bot = await message.bot.get_me()
        await UserService(db).add_conversation(message.from_user.id)
        await processing_msg.delete()
        await message.reply_document(audio_file, caption=f'Converted by @{bot.username}')

        if not r.exists(key):
            r.set(key, 1)
            r.expire(key, 86400)
        else:
            r.incr(key)
    finally:
        os.remove(video_path)
        if audio_path and os.path.exists(audio_path):
            os.remove(audio_path)
