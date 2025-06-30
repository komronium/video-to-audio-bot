import logging
from aiogram import BaseMiddleware
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.exceptions import TelegramAPIError, TelegramForbiddenError

from config import settings
from database.session import get_db
from handlers.start import get_language_keyboard
from services.user_service import UserService
from utils.i18n import i18n


class SubscriptionMiddleware(BaseMiddleware):

    @staticmethod
    async def check_subscription(bot, user_id, channel_id=settings.CHANNEL_ID):
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
                async with get_db() as db:
                    service = UserService(db)
                    lang = await service.get_lang(event.from_user.id)

                    if not lang:
                        return await event.answer(
                            i18n.get_text('choose_language'),
                            reply_markup=get_language_keyboard()
                        )

                    await event.answer(
                        "To continue, please subscribe to our channel first.",
                        reply_markup=SubscriptionMiddleware.subscription_keyboard(lang)
                    )
            except TelegramForbiddenError:
                logging.warning(f"User {user_id} has blocked the bot. Cannot send message.")
            return None

        return await handler(event, data)

    @staticmethod
    def subscription_keyboard(lang: str):
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=i18n.get_text('join-channel', lang), url=settings.CHANNEL_JOIN_LINK)],
            [InlineKeyboardButton(text=i18n.get_text('check-subs', lang), callback_data='check_subscription')]
        ])
        return keyboard
