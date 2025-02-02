import os
from pathlib import Path
from aiogram import Router, F
from aiogram.types import Message, FSInputFile
from sqlalchemy.orm import Session

from services.converter import convert_video_to_audio
from services.user_service import UserService

SIZE_IN_MB = 120

router = Router()


@router.message(F.video)
async def video_handler(message: Message, db: Session):
    video = message.video
    if video.file_size > SIZE_IN_MB * 1024 * 1024:
        await message.bot.send_chat_action(message.chat.id, 'typing')
        await message.reply(f'Sorry, but we can only process files up to {SIZE_IN_MB} MB in size')
        return

    await message.bot.send_chat_action(message.chat.id, 'typing')
    processing_msg = await message.reply("Downloading ...")

    file = await message.bot.get_file(video.file_id)
    video_path = file.file_path
    audio_path = None

    try:
        file_name = Path(video.file_name or video.file_unique_id).stem.lower()

        await processing_msg.edit_text("Converting ...")

        audio_path = convert_video_to_audio(video_path, f'audios/{file_name}')
        audio_file = FSInputFile(path=audio_path)

        bot = await message.bot.get_me()
        await UserService(db).add_conversation(message.from_user.id)
        await processing_msg.delete()
        await message.bot.send_chat_action(message.chat.id, 'upload_document')
        await message.reply_document(audio_file, caption=f'Converted by @{bot.username}')
    finally:
        os.remove(video_path)
        if audio_path and os.path.exists(audio_path):
            os.remove(audio_path)
