from aiogram import BaseMiddleware
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from config import settings


class SubscriptionMiddleware(BaseMiddleware):

    async def __call__(
        self,
        handler,
        event,
        data
    ):
        user_id = event.from_user.id
        chat_member = await event.bot.get_chat_member(settings.CHANNEL_ID, user_id)

        if chat_member.status in ['left', 'kicked', 'banned']:
            await event.answer(
                'To continue, please subscribe to our channel first!',
                reply_markup=SubscriptionMiddleware.subscription_keyboard()
            )
            return

        return await handler(event, data)

    @staticmethod
    def subscription_keyboard():
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text='Join the channel', url=settings.CHANNEL_JOIN_LINK)],
            [InlineKeyboardButton(text='✅ Check subscription', callback_data='check_subscription')]
        ])
        return keyboard
