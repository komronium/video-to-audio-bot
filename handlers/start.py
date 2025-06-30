from aiogram import types, Router
from aiogram.filters import Command

from utils.i18n import i18n

router = Router()


@router.message(Command('start'))
async def command_start(message: types.Message, lang: str):
    await message.reply(i18n.get_text('start', lang))
