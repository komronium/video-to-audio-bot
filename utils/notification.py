import logging
from aiogram import Bot
from sqlalchemy.ext.asyncio import AsyncSession
from config import settings

MESSAGE_TEMPLATE = (
    "<b>New user!</b>\n"
    "<b>Name:</b> {name}"
    "<b>Username:</b> @{username}\n"
    "<b>Language:</b> <code>{lang}</code>\n"
    "<b>Total users:</b> <code>{total}</code>"
)


async def notify_group(bot: Bot, user, db: AsyncSession):
    try:
        from services.user_service import UserService
        service = UserService(db)
        total = await service.total_users()
        lang = getattr(user, 'lang', None) or '—'

        message = MESSAGE_TEMPLATE.format(
            name=user.name,
            username=user.username or 'N/A',
            lang=lang,
            total=total,
        )
        await bot.send_message(settings.GROUP_ID, message.strip())
    except Exception as e:
        logging.error(f"Error while sending notification: {e}")


async def notify_milestone(bot: Bot, total_users: int):
    try:
        milestones = {100, 500, 1000}
        if total_users in milestones or (total_users % 1000 == 0 and total_users > 0):
            text = (
                "🎉 <b>Milestone reached!</b>\n"
                f"👥 Total users: <b>{total_users}</b>\n"
                "🙏 Thanks for being with us!"
            )
            await bot.send_message(settings.GROUP_ID, text)
    except Exception as e:
        logging.error(f"Error while sending milestone notification: {e}")
