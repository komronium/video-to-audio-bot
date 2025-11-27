import asyncio
import logging
from collections import Counter
import io

from aiogram import types, Router, Bot, F
from aiogram.filters import Command
from sqlalchemy.ext.asyncio import AsyncSession
from dataclasses import dataclass

from config import settings
from services.user_service import UserService
from utils.i18n import i18n
from sqlalchemy import func, select
from database.models import User, Payment
from services.stats_service import joins_per_days, create_join_chart_image
from aiogram.types import InputFile
import tempfile
import os
import traceback

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
    # Minimal, emoji-free layout (original)
    pct = max(0.0, min(100.0, stats.active_users_percentage))
    return (
        "<b>Statistics</b>\n\n"
        f"🔹 Users: <code>{stats.total_users}</code>\n"
        f"🔹 Active: <code>{stats.total_active_users}</code> (<code>{pct:.0f}%</code>)\n"
        f"🔹 Conversations: <code>{stats.total_conversations}</code>\n"
        f"🔹 Average per active: <code>{stats.avg_conversations}</code>\n"
        f"🔹 New today: <code>{stats.users_joined_today}</code>"
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


async def langs_internal(message: types.Message, db: AsyncSession):
    user_service = UserService(db)
    langs = await user_service.get_langs()

    text = ''
    for lang in langs:
        if lang:
            text += f"<code>{langs[lang]}</code>\t\t{i18n.get_text('lang', lang)}\n"
        else:
            text += f"<code>{langs[lang]}</code>\t\tNOT SELECTED\n"

    await message.answer(text)


async def deflangs_internal(message: types.Message, db: AsyncSession, bot: Bot):
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
    # Charts are sent by a separate handler/button to avoid blocking
    pass


async def charts_internal(message: types.Message, db: AsyncSession, bot: Bot):
    """Generate and send charts (7d and 30d) to the admin who requested them.

    On error, send the full traceback to the admin's Telegram (settings.ADMIN_ID)
    so they can see exactly what failed.
    """
    if message.from_user.id != settings.ADMIN_ID:
        return

    try:
        dates7, vals7 = await joins_per_days(db, 7)
        buf7 = create_join_chart_image(dates7, vals7, title="New users — last 7 days")
        dates30, vals30 = await joins_per_days(db, 30)
        buf30 = create_join_chart_image(dates30, vals30, title="New users — last 30 days")

        # Write buffers to temporary files because aiogram's InputFile expects a file path
        tmp7 = None
        tmp30 = None
        try:
            with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as f7:
                f7.write(buf7.getvalue())
                tmp7 = f7.name

            with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as f30:
                f30.write(buf30.getvalue())
                tmp30 = f30.name

            await message.answer_photo(photo=InputFile(tmp7), caption="New users — last 7 days")
            await message.answer_photo(photo=InputFile(tmp30), caption="New users — last 30 days")
        finally:
            for p in (tmp7, tmp30):
                try:
                    if p and os.path.exists(p):
                        os.unlink(p)
                except Exception:
                    logging.exception("Failed to delete temp chart file %s", p)
    except Exception:
        tb = traceback.format_exc()
        logging.exception("Chart generation failed")
        # Try to notify admin with exact traceback
        try:
            await bot.send_message(settings.ADMIN_ID, f"❌ Chart generation error:\n<pre>{tb}</pre>", parse_mode="HTML")
        except Exception:
            # If sending to admin fails, log it — nothing else we can do here
            logging.exception("Failed to send chart error traceback to admin")
        # Notify the user who pressed the button (admin) in short form
        try:
            await message.answer('❌ Chart generation failed. Admin has been notified with details.')
        except Exception:
            pass


async def adminstats_internal(message: types.Message, db: AsyncSession):
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

    # Append Top 10 users by conversations
    top_users = await service.get_top_users(limit=10)
    if top_users:
        text += "\n\n<b>Top 10 users</b>\n"
        for idx, user in enumerate(top_users, start=1):
            name = user.name or (f"@{user.username}" if user.username else str(user.user_id))
            text += f"{idx}. {name} — <code>{user.conversation_count}</code>\n"


    await message.answer(text)
