import asyncio
from datetime import date, timedelta, datetime
import redis
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

r = redis.Redis(host='localhost', port=6379, decode_responses=True)


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
    pct = max(0.0, min(100.0, stats.active_users_percentage))
    title = i18n.get_text('stats-title', lang)
    users_label = i18n.get_text('stats-users', lang)
    active_label = i18n.get_text('stats-active', lang)
    conv_label = i18n.get_text('stats-conversations', lang)
    avg_label = i18n.get_text('stats-avg-per-active', lang)
    new_today_label = i18n.get_text('stats-new-today', lang)

    return (
        f"<b>{title}</b>\n\n"
        f"🔹 {users_label}: <code>{stats.total_users}</code>\n"
        f"🔹 {active_label}: <code>{stats.total_active_users}</code> (<code>{pct:.0f}%</code>)\n"
        f"🔹 {conv_label}: <code>{stats.total_conversations}</code>\n"
        f"🔹 {avg_label}: <code>{stats.avg_conversations}</code>\n"
        f"🔹 {new_today_label}: <code>{stats.users_joined_today}</code>"
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

    text = (
        "<b>Admin Statistics</b>\n\n"
        f"🔹 Users: <code>{total_users}</code>\n"
        f"🔹 Active: <code>{total_active}</code> (<code>{active_pct:.0f}%</code>)\n"
        f"🔹 Conversations: <code>{total_conversations}</code>\n"
        f"🔹 Average per active: <code>{avg_conv}</code>\n"
        f"🔹 New users: today <code>{base.get('users_joined_today') or 0}</code> | last 7d <code>{joined_last_week}</code>\n"
        f"🔹 Top languages: {top_langs or '—'}\n"
        f"🔹 Sales — diamonds: <code>{diamonds_total}</code> | lifetime: <code>{lifetime_total}</code>\n"
        f"🔹 Stars (est.): <code>{stars_total}</code>  (diamonds: <code>{stars_from_diamonds}</code>, lifetime: <code>{stars_from_lifetime}</code>)"
    )

    # ===== Activity metrics (DAU/WAU/MAU) and Retention =====
    def active_users_on(day: date) -> set[int]:
        dstr = day.strftime('%Y-%m-%d')
        # Keys like user:{user_id}:{YYYY-MM-DD}
        active_ids: set[int] = set()
        cursor = '0'
        pattern = f"user:*:{dstr}"
        while True:
            cursor, keys = r.scan(cursor=cursor, match=pattern, count=1000)
            for k in keys:
                try:
                    parts = k.split(':')
                    active_ids.add(int(parts[1]))
                except Exception:
                    continue
            if cursor == '0':
                break
        return active_ids

    today_set = active_users_on(today)
    dau = len(today_set)

    def union_over(days: int) -> set[int]:
        s: set[int] = set()
        for i in range(days):
            s |= active_users_on(today - timedelta(days=i))
        return s

    wau = len(union_over(7))
    mau = len(union_over(30))

    # Retention: among today's actives, what % also active 1/7/30 days ago
    def retention_pct(diff_days: int) -> float:
        if not today_set:
            return 0.0
        past = active_users_on(today - timedelta(days=diff_days))
        return round(100.0 * len(today_set & past) / len(today_set), 1)

    r1 = retention_pct(1)
    r7 = retention_pct(7)
    r30 = retention_pct(30)

    text += (
        "\n\n<b>Activity</b>\n"
        f"DAU: <code>{dau}</code> | WAU: <code>{wau}</code> | MAU: <code>{mau}</code>\n"
        f"Retention — 1d: <code>{r1}%</code> | 7d: <code>{r7}%</code> | 30d: <code>{r30}%</code>"
    )

    # ===== Funnel (Start → Upload → Convert → Download) =====
    dstr = today.strftime('%Y-%m-%d')
    start_cnt = int(r.get(f"metrics:funnel:{dstr}:start") or 0)
    upload_cnt = int(r.get(f"metrics:funnel:{dstr}:upload") or 0)
    convert_cnt = int(r.get(f"metrics:funnel:{dstr}:convert") or 0)
    download_cnt = int(r.get(f"metrics:funnel:{dstr}:download") or 0)

    text += (
        "\n\n<b>Funnel (today)</b>\n"
        f"Start: <code>{start_cnt}</code> → Upload: <code>{upload_cnt}</code> → Convert: <code>{convert_cnt}</code> → Download: <code>{download_cnt}</code>"
    )

    # Append Top 10 users by conversations
    top_users = await service.get_top_users(limit=10)
    if top_users:
        text += "\n\n<b>Top 10 users</b>\n"
        for idx, user in enumerate(top_users, start=1):
            name = user.name or (f"@{user.username}" if user.username else str(user.user_id))
            text += f"{idx}. {name} — <code>{user.conversation_count}</code>\n"

    await message.answer(text)
