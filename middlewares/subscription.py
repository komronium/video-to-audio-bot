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
    async def check_subscription(bot, user_id: int, channel_id: int = settings.CHANNEL_ID) -> bool:
        try:
            member = await bot.get_chat_member(channel_id, user_id)
            return member.status not in ("left", "kicked", "banned")
        except TelegramAPIError as e:
            logging.error(f"Error checking subscription for {user_id}: {e}")
            raise

    @staticmethod
    def subscription_keyboard(lang: str) -> InlineKeyboardMarkup:
        return InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=i18n.get_text("join-channel", lang), url=settings.CHANNEL_JOIN_LINK)],
            [InlineKeyboardButton(text=i18n.get_text("check-subs", lang), callback_data="check_subscription")],
        ])

    async def __call__(self, handler, event, data):
        user_id = event.from_user.id

        if not await self.check_subscription(event.bot, user_id):
            try:
                async with get_db() as db:
                    lang = await UserService(db).get_lang(user_id)
                if not lang:
                    await event.answer(
                        i18n.get_text("choose_language"),
                        reply_markup=get_language_keyboard(),
                    )
                else:
                    await event.answer(
                        i18n.get_text("subscribe", lang),
                        reply_markup=self.subscription_keyboard(lang),
                    )
            except TelegramForbiddenError:
                logging.warning(f"User {user_id} has blocked the bot.")
            return None

        return await handler(event, data)
