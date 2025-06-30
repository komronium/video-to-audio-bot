from aiogram import types, Router
from aiogram.filters import Command
from sqlalchemy.ext.asyncio import AsyncSession
from dataclasses import dataclass

from services.user_service import UserService
from utils.i18n import i18n

router = Router()


@dataclass
class Stats:
    total_users: int
    total_active_users: int
    total_conversations: int
    users_joined_today: int

    @property
    def active_users_percentage(self) -> float:
        if not self.total_users:
            return 0.0
        return round(self.total_active_users * 100 / self.total_users)

    @property
    def avg_conversations(self) -> float:
        if not self.total_active_users:
            return 0.0
        return round(self.total_conversations / self.total_active_users, 1)


def format_stats_message(stats: Stats) -> str:
    return (
        f"📊 <b>BOT STATISTICS:</b>\n\n"
        f"🔹 Total Users: <b>{stats.total_users}</b>\n"
        f"🔹 Active Users: <b>{stats.total_active_users}</b> ({stats.active_users_percentage}%)\n"
        f"🔹 Total Conversations: <b>{stats.total_conversations}</b> ({stats.avg_conversations})\n"
        f"🔹 New Users Today: <b>{stats.users_joined_today}</b>"
    )


@router.message(Command('stats'))
async def command_stats(message: types.Message, db: AsyncSession):
    try:
        user_service = UserService(db)
        raw_stats = await user_service.get_stats()
        stats = Stats(**raw_stats)

        text = format_stats_message(stats)
        await message.answer(text)
    except Exception:
        await message.answer('❌ Error getting statistics')
        raise


@router.message(Command('langs'))
async def command_stats(message: types.Message, db: AsyncSession):
    user_service = UserService(db)
    langs = await user_service.get_langs()

    text = ''
    for lang in langs:
        if lang:
            text += f"<code>{langs[lang]}</code>\t\t{i18n.get_text('lang', lang)}\n"
        else:
            text += f"<code>{langs[lang]}</code>\t\tNOT SELECTED\n"

    await message.answer(text)
