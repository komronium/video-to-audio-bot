from aiogram import Bot
from config import settings


async def notify_group(bot: Bot, user):
    try:
        message = (
            f"<b>New User Joined!</b>\n"
            f"<b>Name:</b> {user.name}\n"
            f"<b>Username:</b> @{user.username if user.username else 'N/A'}"
        )
        await bot.send_chat_action(settings.GROUP_ID, 'typing')
        await bot.send_message(settings.GROUP_ID, message)
    except Exception as e:
        print(f"Error notifying group: {e}")
