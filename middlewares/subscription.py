import logging
from aiogram import BaseMiddleware
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.exceptions import TelegramAPIError, TelegramForbiddenError

from config import settings


class SubscriptionMiddleware(BaseMiddleware):

    @staticmethod
    async def check_subscription(bot, user_id, channel_id):
        try:
            member = await bot.get_chat_member(channel_id, user_id)
            is_subscribed = member.status not in ['left', 'kicked', 'banned']
            return is_subscribed
        except TelegramAPIError as e:
            logging.error(f"Error while checking subscription: {e}")
            raise

    async def __call__(
        self,
        handler,
        event,
        data
    ):
        user_id = event.from_user.id

        if not await self.check_subscription(event.bot, user_id, settings.CHANNEL_ID):
            try:
                await event.answer(
                    "To continue, please subscribe to our channel first.",
                    reply_markup=SubscriptionMiddleware.subscription_keyboard()
                )
            except TelegramForbiddenError:
                logging.warning(f"User {user_id} has blocked the bot. Cannot send message.")
            return None

        return await handler(event, data)

    @staticmethod
    def subscription_keyboard():
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text='🔗 Join the Channel', url=settings.CHANNEL_JOIN_LINK)],
            [InlineKeyboardButton(text='✅ Check subscription', callback_data='check_subscription')]
        ])
        return keyboard
