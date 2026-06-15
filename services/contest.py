"""Monthly contest leaderboard.

Tracks two ladders that reset on the first of each month:
  • Conversions this month
  • Referrals (people who made their first conversion this month)

Reward tiers are constants here, intentionally short — adjust to taste.
"""

from calendar import monthrange
from dataclasses import dataclass
from datetime import date, timedelta

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from config import settings
from database.models import Conversion, Referral, User

# Top 3 → (diamonds reward, monthly-premium days). Position 1 also gets
# a month of premium so the prize feels qualitatively distinct.
PRIZES_CONVERSIONS = {1: (30, 30), 2: (20, 0), 3: (10, 0)}
PRIZES_REFERRALS = {1: (50, 30), 2: (25, 0), 3: (10, 0)}


def month_bounds(today: date | None = None) -> tuple[date, date]:
    today = today or date.today()
    start = today.replace(day=1)
    _, last = monthrange(today.year, today.month)
    end = today.replace(day=last)
    return start, end


def days_left_in_month(today: date | None = None) -> int:
    today = today or date.today()
    _, end = month_bounds(today)
    return max((end - today).days, 0)


@dataclass
class LeaderRow:
    user_id: int
    name: str
    username: str | None
    count: int

    def display(self) -> str:
        if self.username:
            return f"@{self.username}"
        return (self.name or str(self.user_id))[:25]


async def top_by_conversions(db: AsyncSession, limit: int = 10) -> list[LeaderRow]:
    start, end = month_bounds()
    end_excl = end + timedelta(days=1)
    rows = await db.execute(
        select(
            Conversion.user_id,
            func.count(Conversion.id).label("c"),
            User.name,
            User.username,
        )
        .join(User, User.user_id == Conversion.user_id)
        .where(
            and_(
                Conversion.created_at >= start,
                Conversion.created_at < end_excl,
                Conversion.user_id != settings.ADMIN_ID,
            )
        )
        .group_by(Conversion.user_id, User.name, User.username)
        .order_by(func.count(Conversion.id).desc())
        .limit(limit)
    )
    return [LeaderRow(uid, name, username, c) for uid, c, name, username in rows.all()]


async def top_by_referrals(db: AsyncSession, limit: int = 10) -> list[LeaderRow]:
    start, end = month_bounds()
    end_excl = end + timedelta(days=1)
    rows = await db.execute(
        select(
            Referral.inviter_id,
            func.count(Referral.id).label("c"),
            User.name,
            User.username,
            User.user_id,
        )
        .join(User, User.id == Referral.inviter_id)
        .where(
            and_(
                Referral.created_at >= start,
                Referral.created_at < end_excl,
            )
        )
        .group_by(Referral.inviter_id, User.name, User.username, User.user_id)
        .order_by(func.count(Referral.id).desc())
        .limit(limit)
    )
    return [LeaderRow(uid, name, username, c) for _, c, name, username, uid in rows.all()]


async def user_rank_conversions(db: AsyncSession, user_id: int) -> tuple[int, int] | None:
    """Returns (rank, count) for the given user this month, or None if zero."""
    start, end = month_bounds()
    end_excl = end + timedelta(days=1)
    my = await db.scalar(
        select(func.count(Conversion.id)).where(
            and_(
                Conversion.user_id == user_id,
                Conversion.created_at >= start,
                Conversion.created_at < end_excl,
            )
        )
    )
    if not my:
        return None
    higher = await db.scalar(
        select(func.count())
        .select_from(
            select(Conversion.user_id, func.count(Conversion.id).label("c"))
            .where(
                and_(
                    Conversion.created_at >= start,
                    Conversion.created_at < end_excl,
                    Conversion.user_id != settings.ADMIN_ID,
                )
            )
            .group_by(Conversion.user_id)
            .having(func.count(Conversion.id) > my)
            .subquery()
        )
    )
    return (higher or 0) + 1, my
