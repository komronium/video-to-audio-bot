from aiogram import types, Router, F
from aiogram.filters import Command
from aiogram.exceptions import TelegramAPIError

from utils.i18n import i18n


router = Router()


@router.message(F.in_([
    i18n.get_text('help-button', lang) for lang in i18n.LANGUAGES
]))
async def command_help(message: types.Message, db: AsyncSession):
    lang = await UserService(db).get_lang(message.from_user.id
    await message.answer(i18n.get_text('help-text', lang))
