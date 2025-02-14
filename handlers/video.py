import os
import redis
from pathlib import Path
from datetime import datetime
from aiogram import Router, F
from aiogram.types import Message, FSInputFile, Document
from sqlalchemy.ext.asyncio import AsyncSession

from services.converter import VideoConverter
from services.user_service import UserService

MAX_FILE_SIZE = 150 * 1024 * 1024
DAILY_LIMIT = 10

r = redis.Redis(host='localhost', port=6379, decode_responses=True)

router = Router()


def generate_name(message: Message) -> str:
    video = message.video

    if message.caption:
        return message.caption.lower().replace(' ', '_')
    
    if video.file_name:
        return video.file_name.rsplit('.', 1)[0].lower().replace(' ', '_')
    
    user_id = message.from_user.id
    timestamp = datetime.now().timestamp()
    return f"audio_{user_id}_{timestamp}.mp3"


@router.message(F.video)
async def video_handler(message: Message, db: AsyncSession, document: Document = None):
    video = message.video if not document else document
    if video.file_size > MAX_FILE_SIZE:
        await message.bot.send_chat_action(message.chat.id, 'typing')
        await message.reply(
            "<b>🚫 File too large!</b>\n"
            "Your video exceeds the 150 MB limit.\n"
            "To remove limits and get premium, click /premium"
        )
        return

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

    processing_msg = await message.reply("Downloading ...")

    file = await message.bot.get_file(video.file_id)
    video_path = file.file_path
    audio_path = None

    try:
        file_name = generate_name(message)

        await processing_msg.edit_text("Converting ...")

        audio_path = await VideoConverter().convert_video_to_audio(video_path, f'audios/{file_name}')
        audio_file = FSInputFile(path=audio_path)

        bot = await message.bot.get_me()
        await UserService(db).add_conversation(message.from_user.id)
        await processing_msg.delete()
        await message.bot.send_chat_action(message.chat.id, 'upload_document')
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


@router.message(F.document.mime_type.startswith('video'))
async def document_handler(message: Message, db: AsyncSession):
    await video_handler(message, db, message.document)
