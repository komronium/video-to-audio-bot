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
from sqlalchemy import func, select
from database.models import User, Payment

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
    def render_progress(pct: float) -> str:
        pct = max(0.0, min(100.0, pct))
        filled = int(round(pct / 10))  # 10-slot bar
        empty = 10 - filled
        return f"|{'█' * filled}{'░' * empty}| {pct:.0f}%"

    # Universal, emoji-forward layout that reads well in any language
    return (
        "📊 <b>Bot Stats</b>\n\n"
        f"👥 Users: <b>{stats.total_users}</b>\n"
        f"🟢 Active: <b>{stats.total_active_users}</b>  {render_progress(stats.active_users_percentage)}\n"
        f"💬 Conversations: <b>{stats.total_conversations}</b>\n"
        f"➗ Avg per active: <b>{stats.avg_conversations}</b>\n"
        f"🆕 Today: <b>{stats.users_joined_today}</b>"
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


@router.message(Command('adminstats'))
async def command_admin_stats(message: types.Message, db: AsyncSession):
    if message.from_user.id != settings.ADMIN_ID:
        return

    # Aggregate core stats (reuse service for base metrics)
    service = UserService(db)
    base = await service.get_stats()

    # Users joined last 7 days
    from datetime import date, timedelta
    today = date.today()
    last_week = today - timedelta(days=6)
    joined_last_week_stmt = select(func.count(User.user_id)).where(User.joined_at >= last_week)
    joined_last_week = (await db.execute(joined_last_week_stmt)).scalar()

    # Top languages
    langs_stmt = select(User.lang, func.count()).where(User.lang.is_not(None)).group_by(User.lang).order_by(func.count().desc()).limit(5)
    langs_rows = (await db.execute(langs_stmt)).all()
    top_langs = ', '.join(f"{lang or '??'}: {count}" for lang, count in langs_rows) if langs_rows else '—'

    # Payments aggregates
    diamonds_sum_stmt = select(func.coalesce(func.sum(Payment.diamonds), 0))
    diamonds_total = (await db.execute(diamonds_sum_stmt)).scalar() or 0

    lifetime_cnt_stmt = select(func.count()).where(Payment.is_lifetime == True)
    lifetime_total = (await db.execute(lifetime_cnt_stmt)).scalar() or 0

    # Revenue in Stars estimation
    stars_from_diamonds = diamonds_total * settings.DIAMONDS_PRICE
    stars_from_lifetime = lifetime_total * settings.LIFETIME_PREMIUM_PRICE
    stars_total = stars_from_diamonds + stars_from_lifetime

    # Active ratio and avg
    total_users = base.get('total_users') or 0
    total_active = base.get('total_active_users') or 0
    total_conversations = base.get('total_conversations') or 0
    active_pct = round((total_active * 100 / total_users), 1) if total_users else 0.0
    avg_conv = round((total_conversations / total_active), 2) if total_active else 0.0

    def render_progress(pct: float) -> str:
        pct = max(0.0, min(100.0, pct))
        filled = int(round(pct / 10))
        empty = 10 - filled
        return f"|{'█' * filled}{'░' * empty}| {pct:.0f}%"

    text = (
        "<b>📊 Admin Stats</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"👥 Users: <b>{total_users}</b>\n"
        f"🟢 Active: <b>{total_active}</b>  {render_progress(active_pct)}\n"
        f"💬 Conversations: <b>{total_conversations}</b>\n"
        f"➗ Avg per active: <b>{avg_conv}</b>\n"
        f"🆕 Today: <b>{base.get('users_joined_today') or 0}</b>  |  7d: <b>{joined_last_week}</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🌐 Top langs: {top_langs}\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"💎 Diamonds sold: <b>{diamonds_total}</b>  |  👑 Lifetime: <b>{lifetime_total}</b>\n"
        f"⭐️ Stars est.: <b>{stars_total}</b>\n"
        f"   ├─ Diamonds: <code>{stars_from_diamonds}</code>\n"
        f"   └─ Lifetime: <code>{stars_from_lifetime}</code>"
    )

    await message.answer(text)
