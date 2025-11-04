import logging
from aiogram import Bot
from config import settings

MESSAGE_TEMPLATE = (
    "🆕 New user joined\n"
    "👤 Name: <b>{name}</b> (@{username})\n"
    "🆔 ID: <code>{user_id}</code>\n"
    "💬 Conversations: <code>{conv}</code>\n"
    "📅 Joined: <code>{joined}</code>"
)


async def notify_group(bot: Bot, user):
    try:
        message = MESSAGE_TEMPLATE.format(
            name=user.name,
            username=user.username or 'N/A',
            user_id=user.user_id,
            conv=user.conversation_count or 0,
            joined=getattr(user, 'joined_at', '')
        )
        await bot.send_message(settings.GROUP_ID, message.strip())
    except Exception as e:
        logging.error(f"Error while sending notification: {e}")
