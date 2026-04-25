from aiogram import types, Router, F

from config import settings
from database.session import get_db
from services.user_service import UserService
from utils.i18n import i18n

router = Router()


@router.callback_query(F.data == "check_subscription")
async def check_subscription_callback(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    member = await callback.bot.get_chat_member(settings.CHANNEL_ID, user_id)

    async with get_db() as db:
        lang = await UserService(db).get_lang(user_id)

    if member.status in ("left", "kicked", "banned"):
        await callback.answer(i18n.get_text("not-sub", lang), show_alert=True)
        return

    try:
        await callback.message.delete()
    except Exception:
        pass
    await callback.message.answer(i18n.get_text("thank-sub", lang))
