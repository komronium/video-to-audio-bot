import os
from pathlib import Path
from aiogram import Router, F
from aiogram.types import Message, FSInputFile
from sqlalchemy.orm import Session

from services.converter import convert_video_to_audio
from services.user_service import UserService

router = Router()


@router.message(F.video)
async def video_handler(message: Message, db: Session):
    video = message.video
    if video.file_size > 100 * 1024 * 1024:
        await message.reply('Sorry, but we can only process files up to 100 MB in size')
        return

    processing_msg = await message.reply("*Processing... Please wait.*")
    file = await message.bot.get_file(video.file_id)
    video_path = file.file_path
    audio_path = None

    try:
        file_name = Path(video.file_name or video.file_unique_id).stem.lower()
        audio_path = convert_video_to_audio(video_path, f'audios/{file_name}')
        audio_file = FSInputFile(path=audio_path)
        await UserService(db).add_conversation(message.from_user.id)
        await processing_msg.delete()
        await message.reply_document(audio_file)
    finally:
        os.remove(video_path)
        if audio_path and os.path.exists(audio_path):
            os.remove(audio_path)
