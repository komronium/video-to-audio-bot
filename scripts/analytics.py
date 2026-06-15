"""Growth & retention analytics for the video-to-audio bot.

Run from the project root:

    python3 -m scripts.analytics

Sections:
  1. Volume — total users, new this week, DAU/WAU/MAU
  2. Cohort retention — D1, D7, D30 for each of the last 8 weekly cohorts
  3. Activation funnel — signed-up → 1 conv → 5 → 10
  4. Conversion mix — video vs. social, last 30 days
  5. Sources — acquisition channel breakdown (requires deep-link tagging)
  6. Top referrers — who's bringing users that actually convert
  7. Drop-off — users registered ≥7 days who never converted; users with
     diamonds but inactive ≥7 days (re-engagement targets)

The script reads the production SQLite DB directly via the configured
DATABASE_URL — read-only, no writes.
"""

import asyncio
import sys
from collections import defaultdict
from datetime import date, datetime, timedelta
from pathlib import Path

# Allow `python3 scripts/analytics.py` as well as `python3 -m scripts.analytics`
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import func, select, and_
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

from config import settings
from database.models import Conversion, Payment, Referral, User


def _pct(num: int, denom: int) -> str:
    if not denom:
        return "  -  "
    return f"{100 * num / denom:5.1f}%"


def _fmt_date(d: date) -> str:
    return d.strftime("%Y-%m-%d")


def _hr(title: str) -> str:
    return f"\n━━━ {title} ━━━"


async def section_volume(session):
    today = date.today()
    week_ago = today - timedelta(days=7)
    month_ago = today - timedelta(days=30)
    day_ago = today - timedelta(days=1)

    total_users = await session.scalar(
        select(func.count(User.user_id)).where(
            and_(User.user_id != settings.ADMIN_ID, User.blocked_at.is_(None))
        )
    )
    total_blocked = await session.scalar(
        select(func.count(User.user_id)).where(User.blocked_at.is_not(None))
    )
    new_today = await session.scalar(
        select(func.count(User.user_id)).where(User.joined_at == today)
    )
    new_7d = await session.scalar(
        select(func.count(User.user_id)).where(User.joined_at >= week_ago)
    )
    new_30d = await session.scalar(
        select(func.count(User.user_id)).where(User.joined_at >= month_ago)
    )

    dau = await session.scalar(
        select(func.count(func.distinct(Conversion.user_id))).where(
            Conversion.created_at == today
        )
    )
    wau = await session.scalar(
        select(func.count(func.distinct(Conversion.user_id))).where(
            Conversion.created_at >= week_ago
        )
    )
    mau = await session.scalar(
        select(func.count(func.distinct(Conversion.user_id))).where(
            Conversion.created_at >= month_ago
        )
    )

    prev_month_start = today - timedelta(days=60)
    prev_mau = await session.scalar(
        select(func.count(func.distinct(Conversion.user_id))).where(
            and_(
                Conversion.created_at >= prev_month_start,
                Conversion.created_at < month_ago,
            )
        )
    )
    delta = (mau or 0) - (prev_mau or 0)
    delta_pct = _pct(abs(delta), prev_mau or 0)
    delta_sign = "+" if delta >= 0 else "-"

    print(_hr("1. VOLUME"))
    print(f"Reachable users (excl blocked & admin) ... {total_users:>6}")
    print(f"Blocked us (lifetime) .................... {total_blocked or 0:>6}")
    print(f"New today / 7d / 30d ........... {new_today:>3} / {new_7d:>4} / {new_30d:>5}")
    print(f"DAU / WAU / MAU ................ {dau or 0:>3} / {wau or 0:>4} / {mau or 0:>5}")
    print(
        f"MAU vs. previous 30d ....... {mau or 0:>5}  vs  {prev_mau or 0:>5}  "
        f"({delta_sign}{abs(delta)}, {delta_pct})"
    )


async def section_retention(session):
    print(_hr("2. COHORT RETENTION (weekly)"))
    print(f"{'cohort start':<14}{'size':>6}{'D1':>8}{'D7':>8}{'D30':>8}")

    today = date.today()
    # 8 weekly cohorts, oldest first
    for weeks_ago in range(8, 0, -1):
        cohort_start = today - timedelta(days=weeks_ago * 7)
        cohort_end = cohort_start + timedelta(days=7)

        cohort_ids = await session.execute(
            select(User.user_id).where(
                and_(User.joined_at >= cohort_start, User.joined_at < cohort_end)
            )
        )
        ids = [r[0] for r in cohort_ids.all()]
        if not ids:
            continue

        async def returned_within(days: int) -> int:
            # "Returned": made a conversion at least `days` after they joined
            # (counted only if `days` has fully elapsed since cohort_end)
            cutoff = today - timedelta(days=days)
            if cohort_start > cutoff:
                return -1  # not enough time elapsed
            # User did at least one conversion on day >= joined_at + days
            stmt = (
                select(func.count(func.distinct(Conversion.user_id)))
                .where(Conversion.user_id.in_(ids))
                .where(Conversion.created_at >= cohort_start + timedelta(days=days))
            )
            return await session.scalar(stmt) or 0

        d1 = await returned_within(1)
        d7 = await returned_within(7)
        d30 = await returned_within(30)

        def cell(returned: int) -> str:
            if returned < 0:
                return f"{'-':>8}"
            return f"{returned:>3} ({_pct(returned, len(ids)).strip()})".rjust(8)

        print(
            f"{_fmt_date(cohort_start):<14}{len(ids):>6}"
            f"{cell(d1)}{cell(d7)}{cell(d30)}"
        )


async def section_activation(session):
    """How far do new users get? Answers 'where do they drop off?'"""
    print(_hr("3. ACTIVATION FUNNEL (users joined in last 30 days)"))
    cutoff = date.today() - timedelta(days=30)

    cohort = await session.execute(
        select(User.user_id, User.conversation_count).where(
            and_(User.joined_at >= cutoff, User.user_id != settings.ADMIN_ID)
        )
    )
    rows = cohort.all()
    total = len(rows)
    if not total:
        print("(no users joined in the last 30 days)")
        return

    counts = [r[1] or 0 for r in rows]
    steps = [
        ("Signed up", total),
        ("≥ 1 conversion", sum(1 for c in counts if c >= 1)),
        ("≥ 2 conversions", sum(1 for c in counts if c >= 2)),
        ("≥ 5 conversions", sum(1 for c in counts if c >= 5)),
        ("≥ 10 conversions", sum(1 for c in counts if c >= 10)),
        ("≥ 25 conversions", sum(1 for c in counts if c >= 25)),
    ]
    for label, count in steps:
        print(f"  {label:<22}{count:>6}  {_pct(count, total)}")


async def section_conversion_mix(session):
    print(_hr("4. CONVERSION MIX (last 30 days)"))
    cutoff = date.today() - timedelta(days=30)
    rows = await session.execute(
        select(Conversion.type, func.count(Conversion.id))
        .where(Conversion.created_at >= cutoff)
        .group_by(Conversion.type)
        .order_by(func.count(Conversion.id).desc())
    )
    data = rows.all()
    total = sum(c for _, c in data)
    if not total:
        print("(no conversions in the last 30 days)")
        return
    for ctype, count in data:
        print(f"  {(ctype or 'unknown'):<14}{count:>6}  {_pct(count, total)}")


async def section_sources(session):
    print(_hr("5. ACQUISITION SOURCES"))
    rows = await session.execute(
        select(User.source, func.count(User.user_id))
        .where(User.user_id != settings.ADMIN_ID)
        .group_by(User.source)
        .order_by(func.count(User.user_id).desc())
        .limit(15)
    )
    data = rows.all()
    if not data or all(s is None for s, _ in data):
        print("(no source attribution yet — start sharing links with")
        print(" ?start=src_<tag>, e.g. ?start=src_tiktok)")
        return
    total = sum(c for _, c in data)
    for src, count in data:
        label = src if src else "(no tag)"
        # Avg conversions per user from this source — quality, not just volume
        avg_conv = await session.scalar(
            select(func.avg(User.conversation_count)).where(
                User.source.is_(src) if src is None else User.source == src
            )
        )
        avg = f"{float(avg_conv or 0):.1f}"
        print(f"  {label:<20}{count:>5}  {_pct(count, total)}  avg conv: {avg}")


async def section_referrers(session):
    print(_hr("6. TOP REFERRERS (last 30 days)"))
    cutoff = date.today() - timedelta(days=30)

    rows = await session.execute(
        select(
            Referral.inviter_id,
            func.count(Referral.id).label("converted"),
        )
        .where(Referral.created_at >= cutoff)
        .group_by(Referral.inviter_id)
        .order_by(func.count(Referral.id).desc())
        .limit(10)
    )
    data = rows.all()
    if not data:
        print("(no successful referrals in the last 30 days)")
        return
    for inviter_pk, converted in data:
        inviter = await session.get(User, inviter_pk)
        if not inviter:
            continue
        name = (inviter.username and f"@{inviter.username}") or inviter.name or str(inviter.user_id)
        print(f"  {name:<25}  converted: {converted:>3}  user_id: {inviter.user_id}")


async def section_dropoff(session):
    print(_hr("7. DROP-OFF / RE-ENGAGEMENT TARGETS"))
    today = date.today()
    week_ago = today - timedelta(days=7)
    month_ago = today - timedelta(days=30)

    # Joined ≥ 7d ago, zero conversions — they registered but never tried
    inactive_new = await session.scalar(
        select(func.count(User.user_id)).where(
            and_(
                User.joined_at <= week_ago,
                User.joined_at > month_ago,
                func.coalesce(User.conversation_count, 0) == 0,
                User.user_id != settings.ADMIN_ID,
            )
        )
    )

    # Users with diamonds in the bank but inactive ≥ 7 days — perfect win-back
    dormant_with_balance = await session.scalar(
        select(func.count(User.user_id)).where(
            and_(
                func.coalesce(User.diamonds, 0) > 0,
                User.is_premium == False,  # noqa: E712
                User.last_active.is_not(None),
                User.last_active < datetime.combine(week_ago, datetime.min.time()),
                User.user_id != settings.ADMIN_ID,
            )
        )
    )

    # Diamond drain — users who used to convert ≥ 5 times but no activity 14+ days
    fourteen_ago = today - timedelta(days=14)
    power_dormant_rows = await session.execute(
        select(User.user_id).where(
            and_(
                func.coalesce(User.conversation_count, 0) >= 5,
                User.last_active.is_not(None),
                User.last_active < datetime.combine(fourteen_ago, datetime.min.time()),
                User.user_id != settings.ADMIN_ID,
            )
        )
    )
    power_dormant = len(power_dormant_rows.all())

    print(f"Registered ≥7d, 0 conversions ........ {inactive_new or 0}")
    print(f"Have 💎 but inactive ≥7d (win-back) ... {dormant_with_balance or 0}")
    print(f"Power users (5+) inactive ≥14d ........ {power_dormant}")


async def main():
    # Use the same DATABASE_URL as the running bot. SQLAlchemy async engine
    # works fine for read-only queries even if the bot has the DB open.
    engine = create_async_engine(settings.DATABASE_URL, echo=False)
    Session = async_sessionmaker(engine, expire_on_commit=False)

    print(f"📊 Bot analytics — generated {datetime.now():%Y-%m-%d %H:%M}")
    async with Session() as session:
        await section_volume(session)
        await section_retention(session)
        await section_activation(session)
        await section_conversion_mix(session)
        await section_sources(session)
        await section_referrers(session)
        await section_dropoff(session)

    await engine.dispose()
    print()


if __name__ == "__main__":
    asyncio.run(main())
