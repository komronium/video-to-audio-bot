from aiogram import types, Router
from aiogram.filters import Command

router = Router()


@router.message(Command('start'))
async def command_start(message: types.Message):
    await message.reply(
        "👋 Hello! Send me a video file, and I will extract its audio for you.\n"
        "🎵 Simply upload a video, and I'll handle the rest!"
    )
