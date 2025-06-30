from aiogram import types, Router, F

from config import settings
from database.session import get_db
from services.user_service import UserService
from utils.i18n import i18n

router = Router()


@router.callback_query(F.data == 'check_subscription')
async def check_subscription(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    chat_member = await callback.bot.get_chat_member(settings.CHANNEL_ID, user_id)

    async with get_db() as db:
        service = UserService(db)
        lang = await service.get_lang(callback.from_user.id)

    if chat_member.status in ['left', 'kicked', 'banned']:
        await callback.answer(
            i18n.get_text('not-sub', lang),
            show_alert=True
        )
        return

    await callback.message.delete()
    await callback.message.answer(i18n.get_text('thank-sub', lang))
