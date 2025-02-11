from aiogram import types, Router
from aiogram.filters import Command

router = Router()


@router.message(Command('start'))
async def command_start(message: types.Message):
    await message.reply(
        "Hello! Please upload your video file, and I'll extract the audio for you. "
        "Just send your video, and I'll handle the rest."
    )
