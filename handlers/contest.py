"""Monthly contest UI.

Users:
    /contest  → see this month's leaderboard, prize tiers, own rank, time left

Admin:
    /award_contest  → list winners + grant prizes, post to admin group
"""

from aiogram import F, Router
from aiogram.exceptions import TelegramAPIError
from aiogram.filters import Command
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from config import settings
from database.session import get_db
from services.contest import (
    PRIZES_CONVERSIONS,
    PRIZES_REFERRALS,
    days_left_in_month,
    top_by_conversions,
    top_by_referrals,
    user_rank_conversions,
)
from services.user_service import UserService
from utils.i18n import i18n

router = Router()


def _medal(pos: int) -> str:
    return {1: "🥇", 2: "🥈", 3: "🥉"}.get(pos, f"<b>{pos}.</b>")


def _format_ladder(rows, title: str, prizes: dict[int, tuple[int, int]], empty: str) -> str:
    lines = [f"<b>{title}</b>"]
    if not rows:
        lines.append(f"<i>{empty}</i>")
        return "\n".join(lines)
    for pos, row in enumerate(rows, start=1):
        prize_text = ""
        if pos in prizes:
            d, days = prizes[pos]
            chunks = []
            if d:
                chunks.append(f"+{d}💎")
            if days:
                chunks.append(f"+{days}d 📅")
            prize_text = f"  · <i>{' · '.join(chunks)}</i>"
        lines.append(f"{_medal(pos)} {row.display()} — <b>{row.count}</b>{prize_text}")
    return "\n".join(lines)


@router.message(Command("contest"))
async def contest_user(message: Message, db: AsyncSession):
    lang = await UserService(db).get_lang(message.from_user.id)
    conversions = await top_by_conversions(db, limit=10)
    referrals = await top_by_referrals(db, limit=10)
    my_rank = await user_rank_conversions(db, message.from_user.id)

    text_parts = [
        i18n.get_text("contest-header", lang).format(days=days_left_in_month()),
        _format_ladder(
            conversions,
            i18n.get_text("contest-ladder-conversions", lang),
            PRIZES_CONVERSIONS,
            i18n.get_text("contest-empty", lang),
        ),
        _format_ladder(
            referrals,
            i18n.get_text("contest-ladder-referrals", lang),
            PRIZES_REFERRALS,
            i18n.get_text("contest-empty", lang),
        ),
    ]
    if my_rank:
        rank, count = my_rank
        text_parts.append(
            i18n.get_text("contest-my-rank", lang).format(rank=rank, count=count)
        )
    else:
        text_parts.append(i18n.get_text("contest-my-rank-none", lang))

    await message.answer("\n\n".join(text_parts))


# ─── Admin: settle the contest ────────────────────────────────────────────


@router.message(Command("award_contest"), F.from_user.id == settings.ADMIN_ID)
async def award_contest(message: Message):
    async with get_db() as db:
        conversions = await top_by_conversions(db, limit=3)
        referrals = await top_by_referrals(db, limit=3)
        service = UserService(db)

        # Grant prizes — idempotent enough for a manual command; rerunning
        # within the same month would double-grant, so flag in chat below.
        granted: list[str] = []
        for pos, row in enumerate(conversions, start=1):
            diamonds, days = PRIZES_CONVERSIONS.get(pos, (0, 0))
            if diamonds:
                await service.add_diamonds(row.user_id, diamonds, record_payment=False)
            if days:
                await service.extend_subscription(row.user_id, days)
            granted.append(
                f"#{pos} conversions · {row.display()} · {row.user_id} · +{diamonds}💎 {'+%dd'%days if days else ''}"
            )
        for pos, row in enumerate(referrals, start=1):
            diamonds, days = PRIZES_REFERRALS.get(pos, (0, 0))
            if diamonds:
                await service.add_diamonds(row.user_id, diamonds, record_payment=False)
            if days:
                await service.extend_subscription(row.user_id, days)
            granted.append(
                f"#{pos} referrals · {row.display()} · {row.user_id} · +{diamonds}💎 {'+%dd'%days if days else ''}"
            )

        # Notify each winner individually in their language. A user can win
        # both ladders; notify once.
        winners = {row.user_id: row for row in [*conversions, *referrals]}
        for row in winners.values():
            try:
                user_lang = await service.get_lang(row.user_id)
                await message.bot.send_message(
                    row.user_id,
                    i18n.get_text("contest-winner-notify", user_lang),
                )
            except TelegramAPIError:
                pass

    summary = "🏆 <b>Contest awarded</b>\n\n" + ("\n".join(granted) if granted else "(no participants)")
    await message.answer(summary)
    try:
        await message.bot.send_message(settings.GROUP_ID, summary)
    except TelegramAPIError:
        pass
