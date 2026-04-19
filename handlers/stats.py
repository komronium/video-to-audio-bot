import asyncio
import logging
from collections import Counter
from datetime import date, timedelta

from aiogram import Bot, F, Router, types
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from config import settings
from database.models import Payment, User
from services.user_service import UserService
from utils.i18n import i18n

router = Router()

MEDALS = {1: "🥇", 2: "🥈", 3: "🥉"}


def _fmt(n: int) -> str:
    return f"{n:,}"


@router.message(
    F.text.in_([i18n.get_text("stats-button", lang) for lang in i18n.LANGUAGES])
)
async def command_stats(message: types.Message, db: AsyncSession):
    try:
        service = UserService(db)
        lang = await service.get_lang(message.from_user.id)
        raw = await service.get_stats()

        total = raw["total_users"] or 0
        active = raw["total_active_users"] or 0
        convs = raw["total_conversations"] or 0
        today = raw["users_joined_today"] or 0
        pct = round(active * 100 / total) if total else 0

        text = i18n.get_text("stat-text", lang).format(
            total=_fmt(total),
            active=_fmt(active),
            pct=pct,
            conversions=_fmt(convs),
            today=today,
        )
        await message.answer(text)
    except Exception:
        await message.answer("❌ Error getting statistics")
        raise


async def langs_internal(message: types.Message, db: AsyncSession):
    service = UserService(db)
    langs = await service.get_langs()

    text = ""
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

    text = ""
    for lang, count in langs.items():
        text += f"<code>{lang} | {count}</code>\n"

    await message.answer(text)


async def adminstats_internal(message: types.Message, db: AsyncSession):
    if message.from_user.id != settings.ADMIN_ID:
        return

    service = UserService(db)
    base = await service.get_stats()

    total_users = base.get("total_users") or 0
    total_active = base.get("total_active_users") or 0
    total_convs = base.get("total_conversations") or 0
    today_joined = base.get("users_joined_today") or 0
    active_pct = round(total_active * 100 / total_users) if total_users else 0
    avg_conv = round(total_convs / total_active, 1) if total_active else 0

    today = date.today()
    week_ago = today - timedelta(days=6)
    week_stmt = select(func.count(User.user_id)).where(User.joined_at >= week_ago)
    week_joined = (await db.execute(week_stmt)).scalar() or 0

    langs_stmt = (
        select(User.lang, func.count())
        .where(User.lang.is_not(None))
        .group_by(User.lang)
        .order_by(func.count().desc())
        .limit(5)
    )
    langs_rows = (await db.execute(langs_stmt)).all()
    top_langs = " · ".join(
        f"{lang or '??'}: {_fmt(c)}" for lang, c in langs_rows
    ) if langs_rows else "—"

    diamonds_stmt = select(func.coalesce(func.sum(Payment.diamonds), 0))
    diamonds_total = (await db.execute(diamonds_stmt)).scalar() or 0

    lifetime_stmt = select(func.count()).where(Payment.is_lifetime == True)
    lifetime_total = (await db.execute(lifetime_stmt)).scalar() or 0

    _prices = settings.DIAMONDS_PRICES
    _avg_price = sum(_prices.values()) / sum(_prices.keys()) if _prices else 0
    stars_diamonds = int(diamonds_total * _avg_price)
    stars_lifetime = lifetime_total * settings.LIFETIME_PREMIUM_PRICE
    stars_total = stars_diamonds + stars_lifetime

    text = (
        "📊 <b>Admin Dashboard</b>\n"
        "━━━━━━━━━━━━━━━\n\n"

        "👥 <b>Users</b>\n"
        f"├ Total: <code>{_fmt(total_users)}</code>\n"
        f"├ Active: <code>{_fmt(total_active)}</code> ({active_pct}%)\n"
        f"├ Avg per user: <code>{avg_conv}</code>\n"
        f"├ Today: <code>+{today_joined}</code> · 7d: <code>+{week_joined}</code>\n"
        f"└ Langs: {top_langs}\n\n"

        "🎧 <b>Conversions</b>\n"
        f"└ Total: <code>{_fmt(total_convs)}</code>\n\n"

        "💰 <b>Revenue</b>\n"
        f"├ 💎 Diamonds sold: <code>{_fmt(diamonds_total)}</code>\n"
        f"├ 👑 Lifetime: <code>{lifetime_total}</code>\n"
        f"└ ⭐ Stars (est.): <code>{_fmt(stars_total)}</code>"
    )

    top_users = await service.get_top_users(limit=10)
    if top_users:
        text += "\n\n🏆 <b>Top 10</b>\n"
        for idx, user in enumerate(top_users, start=1):
            medal = MEDALS.get(idx, f"<code>{idx}.</code>")
            name = user.name or (
                f"@{user.username}" if user.username else str(user.user_id)
            )
            text += f"{medal} {name} — <code>{user.conversation_count}</code>\n"

    await message.answer(text)
