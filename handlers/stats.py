import asyncio
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


def format_stats_message(stats: Stats, lang: str) -> str:
    return i18n.get_text('stat-text', lang).format(
        stats.total_users,
        stats.total_active_users,
        stats.active_users_percentage,
        stats.total_conversations,
        stats.avg_conversations,
        stats.users_joined_today
    )


@router.message(F.text.in_([
    i18n.get_text('stats-button', lang) for lang in i18n.LANGUAGES
]))
async def command_stats(message: types.Message, db: AsyncSession):
    try:
        user_service = UserService(db)
        lang = await user_service.get_lang(message.from_user.id)
        raw_stats = await user_service.get_stats()
        stats = Stats(**raw_stats)

        text = format_stats_message(stats, lang)
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

    async def get_lang(user):
        try:
            user_info = await bot.get_chat_member(settings.CHANNEL_ID, user.user_id)
            return user_info.user.language_code
        except Exception as e:
            logging.error(e)
            return None

    results = await asyncio.gather(*(get_lang(user) for user in users))

    for lang in results:
        if lang:
            langs[lang] = langs.get(lang, 0) + 1

    langs = Counter(langs)
    langs = dict(langs.most_common(10))


    text = ''
    for lang, count in langs.items():
        text += f"<code>{lang} | {count}</code>\n"

    await message.answer(text)
