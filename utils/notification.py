import logging
from aiogram import Bot
from config import settings

MESSAGE_TEMPLATE = (
    "<b>New User Joined!</b>\n"
    "<b>Name:</b> {name}\n"
    "<b>Username:</b> @{username}"
)


async def notify_group(bot: Bot, user):
    try:
        message = MESSAGE_TEMPLATE.format(
            name=user.name,
            username=user.username or 'N/A'
        )
        await bot.send_chat_action(settings.GROUP_ID, 'typing')
        await bot.send_message(settings.GROUP_ID, message.strip())
    except Exception as e:
        logging.error(f"Error while sending notification: {e}")
