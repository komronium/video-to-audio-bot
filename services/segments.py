"""User-segment selectors for broadcasts.

Each segment is computed at send-time, not pre-selection — the audience
size shown to the admin matches what will actually be messaged, with no
staleness between picker and confirm.
"""

from dataclasses import dataclass
from datetime import date, datetime, timedelta

from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from config import settings
from database.models import Conversion, User

ACTIVE_DAYS = 30
DORMANT_DAYS = 30

# Segments declared in the order they should appear in the picker UI.
SEGMENTS = {
    "all":        "👥 All users",
    "active":     f"🟢 Active (last {ACTIVE_DAYS}d)",
    "dormant":    f"😴 Dormant ({DORMANT_DAYS}d+ inactive)",
    "premium":    "👑 Premium (lifetime or monthly)",
    "diamonds":   "💎 Has diamonds (>0)",
    "top_100":    "🏆 Top 100 by conversions",
    "by_lang":    "🌍 By language…",
}


@dataclass
class SegmentResult:
    label: str
    user_ids: list[int]


# All segments share this baseline: never message the admin, never message
# users we already know blocked us.
def _base_filter():
    return and_(User.user_id != settings.ADMIN_ID, User.blocked_at.is_(None))


async def _all(db: AsyncSession) -> list[int]:
    rows = await db.execute(select(User.user_id).where(_base_filter()))
    return [r[0] for r in rows.all()]


async def _active(db: AsyncSession) -> list[int]:
    """Made at least one conversion in the last N days."""
    cutoff = date.today() - timedelta(days=ACTIVE_DAYS)
    rows = await db.execute(
        select(User.user_id)
        .join(Conversion, Conversion.user_id == User.user_id)
        .where(and_(_base_filter(), Conversion.created_at >= cutoff))
        .group_by(User.user_id)
    )
    return [r[0] for r in rows.all()]


async def _dormant(db: AsyncSession) -> list[int]:
    """No conversion in the last N days and joined more than N days ago."""
    cutoff = date.today() - timedelta(days=DORMANT_DAYS)
    active_subq = select(func.distinct(Conversion.user_id)).where(
        Conversion.created_at >= cutoff
    )
    rows = await db.execute(
        select(User.user_id).where(
            and_(
                _base_filter(),
                User.user_id.not_in(active_subq),
                User.joined_at <= cutoff,
            )
        )
    )
    return [r[0] for r in rows.all()]


async def _premium(db: AsyncSession) -> list[int]:
    today = date.today()
    rows = await db.execute(
        select(User.user_id).where(
            and_(
                _base_filter(),
                or_(
                    User.is_premium == True,  # noqa: E712
                    User.subscription_until >= today,
                ),
            )
        )
    )
    return [r[0] for r in rows.all()]


async def _has_diamonds(db: AsyncSession) -> list[int]:
    rows = await db.execute(
        select(User.user_id).where(
            and_(
                _base_filter(),
                func.coalesce(User.diamonds, 0) > 0,
                User.is_premium == False,  # noqa: E712
            )
        )
    )
    return [r[0] for r in rows.all()]


async def _top(db: AsyncSession, n: int = 100) -> list[int]:
    rows = await db.execute(
        select(User.user_id)
        .where(_base_filter())
        .order_by(func.coalesce(User.conversation_count, 0).desc())
        .limit(n)
    )
    return [r[0] for r in rows.all()]


async def _by_lang(db: AsyncSession, lang: str) -> list[int]:
    rows = await db.execute(
        select(User.user_id).where(and_(_base_filter(), User.lang == lang))
    )
    return [r[0] for r in rows.all()]


async def resolve_segment(db: AsyncSession, key: str) -> SegmentResult:
    """Returns a fresh user-id list for the chosen segment."""
    if key == "all":
        return SegmentResult(SEGMENTS["all"], await _all(db))
    if key == "active":
        return SegmentResult(SEGMENTS["active"], await _active(db))
    if key == "dormant":
        return SegmentResult(SEGMENTS["dormant"], await _dormant(db))
    if key == "premium":
        return SegmentResult(SEGMENTS["premium"], await _premium(db))
    if key == "diamonds":
        return SegmentResult(SEGMENTS["diamonds"], await _has_diamonds(db))
    if key == "top_100":
        return SegmentResult(SEGMENTS["top_100"], await _top(db, 100))
    if key.startswith("lang:"):
        lang = key.split(":", 1)[1]
        return SegmentResult(f"🌍 Language: {lang}", await _by_lang(db, lang))
    return SegmentResult(key, [])
