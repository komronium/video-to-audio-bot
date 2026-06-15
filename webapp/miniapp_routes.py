"""User-facing Mini App endpoints.

All routes require a valid Telegram WebApp ``initData`` header — that's how
we know the request really came from a Telegram client and which user it
is. The HMAC validation follows the Telegram WebApp docs verbatim.

Endpoints:
    POST /api/miniapp/me          → profile, status, streak, daily limit
    POST /api/miniapp/referrals   → link, stats, top inviters
    POST /api/miniapp/contest     → leaderboards + own rank + days left

Each request body just carries the raw initData string the WebApp gave us
from ``window.Telegram.WebApp.initData``; nothing else is trusted.
"""

import hashlib
import hmac
import json
import os
from calendar import monthrange
from datetime import date, datetime, timedelta
from pathlib import Path
from urllib.parse import parse_qsl

from dotenv import load_dotenv
from fastapi import APIRouter, Body, HTTPException
from sqlalchemy import MetaData, create_engine, and_, func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

BOT_TOKEN = os.getenv("BOT_TOKEN", "")
DB_PATH = Path(__file__).resolve().parent.parent / "database.db"
DATABASE_URL = f"sqlite+aiosqlite:///{DB_PATH}"
DAILY_LIMIT = 3

# initData TTL: requests older than 24h are rejected (Telegram's recommended
# anti-replay window). We don't worry about exact clock skew at this scale.
INIT_DATA_MAX_AGE = 86_400

_engine = create_async_engine(DATABASE_URL, echo=False)
_Session = async_sessionmaker(bind=_engine, expire_on_commit=False)
_sync_engine = create_engine(f"sqlite:///{DB_PATH}")


def _verify_init_data(init_data: str) -> dict:
    """Returns the parsed dict on success, raises HTTPException on failure."""
    if not BOT_TOKEN:
        raise HTTPException(500, "BOT_TOKEN not configured")
    try:
        parsed = dict(parse_qsl(init_data, strict_parsing=True))
    except ValueError:
        raise HTTPException(401, "Malformed initData")

    received_hash = parsed.pop("hash", None)
    if not received_hash:
        raise HTTPException(401, "Missing hash")

    data_check_string = "\n".join(
        f"{k}={v}" for k, v in sorted(parsed.items())
    )
    secret_key = hmac.new(
        b"WebAppData", BOT_TOKEN.encode(), hashlib.sha256
    ).digest()
    expected_hash = hmac.new(
        secret_key, data_check_string.encode(), hashlib.sha256
    ).hexdigest()
    if not hmac.compare_digest(received_hash, expected_hash):
        raise HTTPException(401, "Invalid initData hash")

    auth_date = int(parsed.get("auth_date", "0"))
    if auth_date and (datetime.utcnow().timestamp() - auth_date) > INIT_DATA_MAX_AGE:
        raise HTTPException(401, "initData expired")

    user = parsed.get("user")
    if not user:
        raise HTTPException(401, "No user in initData")
    parsed["user"] = json.loads(user)
    return parsed


async def _get_user(session, user_id: int):
    """Light raw-SQL fetch — avoids importing the bot's User model (would
    pull half the project) and keeps this module self-contained."""
    users_t = _users_table()
    row = (await session.execute(
        select(
            users_t.c.id,
            users_t.c.user_id,
            users_t.c.name,
            users_t.c.username,
            users_t.c.conversation_count,
            users_t.c.joined_at,
            users_t.c.diamonds,
            users_t.c.is_premium,
            users_t.c.lang,
            users_t.c.referral_code,
            users_t.c.subscription_until,
            users_t.c.blocked_at,
        ).where(
            users_t.c.user_id == user_id
        )
    )).first()
    return dict(row._mapping) if row else None


# Reflect the live schema once so we don't duplicate models here.
_TABLES = {}


def _refl():
    """Lazy: only reflect when first needed (avoids work at import time)."""
    if "users" in _TABLES:
        return _TABLES
    md = MetaData()
    md.reflect(bind=_sync_engine, only=("users", "conversions", "referrals"))
    for tbl in md.tables.values():
        _TABLES[tbl.name] = tbl
    return _TABLES


def _users_table():
    return _refl()["users"]


def _conversions_table():
    return _refl()["conversions"]


def _referrals_table():
    return _refl()["referrals"]


def _is_active_premium(user: dict) -> bool:
    if user.get("is_premium"):
        return True
    su = user.get("subscription_until")
    return bool(su and su >= date.today())


def _month_bounds() -> tuple[date, date]:
    today = date.today()
    start = today.replace(day=1)
    _, last = monthrange(today.year, today.month)
    return start, today.replace(day=last)


router = APIRouter(prefix="/api/miniapp", tags=["miniapp"])


# ─── /me ────────────────────────────────────────────────────────────────


@router.post("/me")
async def me(init_data: str = Body(..., embed=True)):
    auth = _verify_init_data(init_data)
    tg_user = auth["user"]
    tg_id = tg_user["id"]

    async with _Session() as session:
        user = await _get_user(session, tg_id)
        if not user:
            raise HTTPException(404, "User not registered — open the bot first")

        conv_count = await session.scalar(
            select(func.count(_conversions_table().c.id)).where(
                _conversions_table().c.user_id == tg_id
            )
        )

        # Today's free-tier counter — Redis would be authoritative but the bot
        # owns that; we mirror by counting today's conversions here, which is
        # good enough for the dashboard display.
        today = date.today()
        used_today = await session.scalar(
            select(func.count(_conversions_table().c.id)).where(
                and_(
                    _conversions_table().c.user_id == tg_id,
                    _conversions_table().c.created_at == today,
                )
            )
        )

        rank = await session.scalar(
            select(func.count()).select_from(_users_table()).where(
                func.coalesce(_users_table().c.conversation_count, 0)
                > (user.get("conversation_count") or 0)
            )
        )
        rank = (rank or 0) + 1

        is_lifetime = bool(user["is_premium"])
        active = _is_active_premium(user)
        status = "lifetime" if is_lifetime else ("monthly" if active else "free")

    return {
        "id": user["user_id"],
        "name": user["name"],
        "username": user["username"],
        "lang": user["lang"] or "en",
        "diamonds": user["diamonds"] or 0,
        "conversions": conv_count or 0,
        "used_today": used_today or 0,
        "daily_limit": DAILY_LIMIT,
        "rank": rank,
        "joined": user["joined_at"].isoformat() if user["joined_at"] else None,
        "status": status,
        "subscription_until": (
            user["subscription_until"].isoformat()
            if user["subscription_until"] else None
        ),
    }


# ─── /referrals ─────────────────────────────────────────────────────────


@router.post("/referrals")
async def referrals(init_data: str = Body(..., embed=True)):
    auth = _verify_init_data(init_data)
    tg_id = auth["user"]["id"]

    async with _Session() as session:
        user = await _get_user(session, tg_id)
        if not user:
            raise HTTPException(404, "User not found")

        users_t = _users_table()
        refs_t = _referrals_table()

        invited_total = await session.scalar(
            select(func.count()).select_from(users_t).where(
                users_t.c.referral_code_id == user["id"]
            )
        )
        converted = await session.scalar(
            select(func.count()).select_from(refs_t).where(
                refs_t.c.inviter_id == user["id"]
            )
        )

    return {
        "code": user.get("referral_code"),
        "invited": int(invited_total or 0),
        "converted": int(converted or 0),
        "earned_diamonds": int((converted or 0) * 5),
    }


# ─── /contest ───────────────────────────────────────────────────────────


@router.post("/contest")
async def contest(init_data: str = Body(..., embed=True)):
    auth = _verify_init_data(init_data)
    tg_id = auth["user"]["id"]

    start, end = _month_bounds()
    end_excl = end + timedelta(days=1)
    today = date.today()
    days_left = max((end - today).days, 0)

    async with _Session() as session:
        c_t = _conversions_table()
        u_t = _users_table()
        r_t = _referrals_table()

        top_conv = (await session.execute(
            select(
                c_t.c.user_id,
                func.count(c_t.c.id).label("c"),
                u_t.c.name,
                u_t.c.username,
            )
            .select_from(c_t.join(u_t, u_t.c.user_id == c_t.c.user_id))
            .where(and_(c_t.c.created_at >= start, c_t.c.created_at < end_excl))
            .group_by(c_t.c.user_id, u_t.c.name, u_t.c.username)
            .order_by(func.count(c_t.c.id).desc())
            .limit(10)
        )).all()

        top_ref = (await session.execute(
            select(
                r_t.c.inviter_id,
                func.count(r_t.c.id).label("c"),
                u_t.c.name,
                u_t.c.username,
                u_t.c.user_id,
            )
            .select_from(r_t.join(u_t, u_t.c.id == r_t.c.inviter_id))
            .where(and_(r_t.c.created_at >= start, r_t.c.created_at < end_excl))
            .group_by(r_t.c.inviter_id, u_t.c.name, u_t.c.username, u_t.c.user_id)
            .order_by(func.count(r_t.c.id).desc())
            .limit(10)
        )).all()

        my_count = await session.scalar(
            select(func.count(c_t.c.id)).where(
                and_(
                    c_t.c.user_id == tg_id,
                    c_t.c.created_at >= start,
                    c_t.c.created_at < end_excl,
                )
            )
        ) or 0
        my_rank = None
        if my_count > 0:
            higher = await session.scalar(
                select(func.count()).select_from(
                    select(c_t.c.user_id, func.count(c_t.c.id).label("c"))
                    .where(and_(c_t.c.created_at >= start, c_t.c.created_at < end_excl))
                    .group_by(c_t.c.user_id)
                    .having(func.count(c_t.c.id) > my_count)
                    .subquery()
                )
            )
            my_rank = (higher or 0) + 1

    def _name(row, name_idx, username_idx) -> str:
        username = row[username_idx]
        name = row[name_idx]
        return f"@{username}" if username else (name or "?")[:24]

    return {
        "days_left": days_left,
        "top_conversions": [
            {"name": _name(row, 2, 3), "count": row[1]}
            for row in top_conv
        ],
        "top_referrals": [
            {"name": _name(row, 2, 3), "count": row[1]}
            for row in top_ref
        ],
        "my_rank": my_rank,
        "my_count": int(my_count),
    }
