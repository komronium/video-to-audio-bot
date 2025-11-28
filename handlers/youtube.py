
import re
from aiogram import Router, F
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from services.user_service import UserService
from utils.i18n import i18n

YOUTUBE_REGEX = r'.*(youtu.*be.*)\/(watch\?v=|embed\/|v|shorts|)(.*?((?=[&#?])|$)).*'

router = Router()


@router.message(F.text.regexp(YOUTUBE_REGEX))
async def youtube_video_handler(message: Message, db: AsyncSession):
    """Temporarily disable the YouTube handler — show a polite message.

    The YouTube conversion feature has been temporarily disabled because it increases the
    processing queue and causes backend instability. Inform the user and do nothing else.
    """
    try:
        user_service = UserService(db)
        lang = await user_service.get_lang(message.from_user.id)
    except Exception:
        # If DB fails, fall back to default language
        lang = 'en'

    text = i18n.get_text('youtube-disabled', lang) or (
        "🔁 YouTube conversions are temporarily disabled because they cause heavy processing queues. We'll bring this feature back soon."
    )
    await message.reply(text)
