import logging
from collections import Counter

from aiogram import types, Router, Bot, F
from aiogram.filters import Command
from sqlalchemy.ext.asyncio import AsyncSession
from dataclasses import dataclass

from config import settings
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
        f"🔹 Total Users: <code>{stats.total_users}</code>\n"
        f"🔹 Active Users: <code>{stats.total_active_users} ({stats.active_users_percentage}%)</code>\n"
        f"🔹 Total Conversations: <code>{stats.total_conversations} ({stats.avg_conversations})</code>\n"
        f"🔹 New Users Today: <code>{stats.users_joined_today}</code>"
    )


@router.message(F.text.in_([
    i18n.get_text('stats-button', lang) for lang in i18n.LANGUAGES
]))
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


@router.message(Command('deflangs'))
async def command_deflang(message: types.Message, db: AsyncSession, bot: Bot):
    service = UserService(db)
    users = await service.get_all_users()
    langs = dict()

    for user in users:
        try:
            user_info = await bot.get_chat_member(settings.CHANNEL_ID, user.user_id)
            lang = user_info.user.language_code

            if lang not in langs:
                langs[lang] = 1
            else:
                langs[lang] += 1
        except Exception as e:
            logging.error(e)

    del langs[None]
    langs = Counter(langs)
    langs = dict(langs.most_common(10))

    text = ''
    for lang in langs:
        if lang:
            text += f"<code>{lang} | {langs[lang]}</code>\n"

    await message.answer(text)
