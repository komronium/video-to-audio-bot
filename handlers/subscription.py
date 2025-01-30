from aiogram import types, Router, F

from config import settings
from middlewares.subscription import SubscriptionMiddleware

router = Router()


@router.callback_query(F.data == 'check_subscription')
async def check_subscription(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    chat_member = await callback.bot.get_chat_member(settings.CHANNEL_ID, user_id)

    if chat_member.status in ['left', 'kicked', 'banned']:
        await callback.answer(
            "❌ You haven't subscribed to the channel yet. Please subscribe to continue!",
            show_alert=True
        )
        return

    await callback.message.delete()
    await callback.message.answer('✅ Thank you for subscribing! You can now use the bot')
