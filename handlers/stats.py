from aiogram import types, Router
from aiogram.filters import Command
from sqlalchemy.orm import Session

from services.user_service import UserService

router = Router()


@router.message(Command('stats'))
async def command_stats(message: types.Message, db: Session):
    user_service = UserService(db)
    stats = user_service.get_stats()

    active_users_perc = round(stats['total_active_users'] * 100 / stats['total_users'])
    avg_conversations_per_active_user = round(stats['total_conversations'] / stats['total_active_users'], 1)

    text = (
        f"📊 <b>Bot Statistics:</b>\n\n"
        f"🔹 Total users: <b>{stats['total_users']}</b>\n"
        f"🔹 Active users: <b>{stats['total_active_users']}</b> ({active_users_perc} %)\n"
        f"🔹 Total conversations: <b>{stats['total_conversations']}</b>\n"
        f"🔹 Avg conversations per active user: <b>{avg_conversations_per_active_user}</b>\n"
        f"🔹 Users joined today: <b>{stats['users_joined_today']}</b>"
    )

    await message.answer(text)
