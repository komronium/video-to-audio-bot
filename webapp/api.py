"""Admin Dashboard API for Video-to-Audio Bot."""

import os
import io
import csv
import json
import uuid
import asyncio
import jwt
import httpx
from datetime import datetime, timedelta, date
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

from fastapi import FastAPI, Depends, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import Optional
from sqlalchemy import (
    Column, Integer, String, Boolean, Date, ForeignKey,
    func, select, distinct,
)
from sqlalchemy.ext.asyncio import (
    create_async_engine, AsyncSession, async_sessionmaker,
)
from sqlalchemy.orm import declarative_base

# ─── Config ───────────────────────────────────────────────

DB_PATH = Path(__file__).resolve().parent.parent / "database.db"
DATABASE_URL = f"sqlite+aiosqlite:///{DB_PATH}"
SECRET_KEY = os.getenv("ADMIN_SECRET", "change-me-in-production")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "admin")
BOT_TOKEN = os.getenv("BOT_TOKEN", "")
ALGORITHM = "HS256"
TOKEN_EXPIRE_HOURS = 24

# ─── Database ─────────────────────────────────────────────

engine = create_async_engine(DATABASE_URL, echo=False)
SessionLocal = async_sessionmaker(
    bind=engine, expire_on_commit=False, class_=AsyncSession
)
Base = declarative_base()


class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, unique=True, nullable=False)
    name = Column(String)
    username = Column(String, nullable=True)
    conversation_count = Column(Integer, default=0)
    joined_at = Column(Date, default=date.today)
    diamonds = Column(Integer, default=0)
    is_premium = Column(Boolean, default=False)
    lang = Column(String(2), nullable=True)


class Conversion(Base):
    __tablename__ = "conversions"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    success = Column(Boolean, default=True)
    is_premium = Column(Boolean, default=False)
    type = Column(String, default="video", nullable=True)
    created_at = Column(Date, default=date.today)


class Payment(Base):
    __tablename__ = "payments"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    diamonds = Column(Integer, default=0)
    is_lifetime = Column(Boolean, default=False)
    created_at = Column(Date, default=date.today)


# ─── Dependencies ─────────────────────────────────────────

async def get_db():
    async with SessionLocal() as session:
        yield session


security = HTTPBearer()


def verify_token(creds: HTTPAuthorizationCredentials = Depends(security)):
    try:
        payload = jwt.decode(creds.credentials, SECRET_KEY, algorithms=[ALGORITHM])
        if payload.get("role") != "admin":
            raise HTTPException(403, "Not admin")
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(401, "Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(401, "Invalid token")


# ─── Schemas ──────────────────────────────────────────────

class LoginRequest(BaseModel):
    password: str


class DiamondRequest(BaseModel):
    count: int


class PremiumRequest(BaseModel):
    is_premium: bool


class BroadcastRequest(BaseModel):
    text: str
    parse_mode: Optional[str] = "HTML"


# ─── App ──────────────────────────────────────────────────

STATIC_DIR = Path(__file__).resolve().parent / "frontend" / "dist"

app = FastAPI(title="Bot Admin API")


@app.on_event("startup")
async def startup():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ─── Auth ─────────────────────────────────────────────────

@app.post("/api/login")
async def login(body: LoginRequest):
    if body.password != ADMIN_PASSWORD:
        raise HTTPException(401, "Wrong password")
    token = jwt.encode(
        {
            "role": "admin",
            "exp": datetime.utcnow() + timedelta(hours=TOKEN_EXPIRE_HOURS),
        },
        SECRET_KEY,
        algorithm=ALGORITHM,
    )
    return {"token": token}


# ─── Helpers ─────────────────────────────────────────────

DIAMOND_PRICE = {1: 2, 3: 5, 5: 8, 10: 15, 20: 28, 50: 70}

def payment_stars(diamonds: int, is_lifetime: bool) -> int:
    if is_lifetime:
        return 200
    return DIAMOND_PRICE.get(diamonds, diamonds * 2)


# ─── Dashboard ────────────────────────────────────────────

@app.get("/api/dashboard")
async def dashboard(
    db: AsyncSession = Depends(get_db),
    _=Depends(verify_token),
):
    today = date.today()
    week_ago = today - timedelta(days=7)
    two_weeks_ago = today - timedelta(days=14)

    total_users = (
        await db.execute(select(func.count(User.user_id)))
    ).scalar() or 0
    active_users = (
        await db.execute(select(func.count(distinct(Conversion.user_id))))
    ).scalar() or 0
    total_conversions = (
        await db.execute(select(func.count(Conversion.id)))
    ).scalar() or 0
    new_today = (
        await db.execute(
            select(func.count(User.user_id)).where(User.joined_at == today)
        )
    ).scalar() or 0
    new_week = (
        await db.execute(
            select(func.count(User.user_id)).where(User.joined_at >= week_ago)
        )
    ).scalar() or 0
    new_prev_week = (
        await db.execute(
            select(func.count(User.user_id)).where(
                User.joined_at >= two_weeks_ago, User.joined_at < week_ago
            )
        )
    ).scalar() or 0
    premium_users = (
        await db.execute(
            select(func.count(User.user_id)).where(User.is_premium == True)
        )
    ).scalar() or 0
    today_conversions = (
        await db.execute(
            select(func.count(Conversion.id)).where(Conversion.created_at == today)
        )
    ).scalar() or 0

    # Growth rate: this week vs prev week
    growth_rate = round(
        ((new_week - new_prev_week) / new_prev_week * 100) if new_prev_week else 0, 1
    )

    # Revenue
    payments_rows = (await db.execute(select(Payment.diamonds, Payment.is_lifetime))).all()
    diamonds_sold = sum(p.diamonds for p in payments_rows if not p.is_lifetime)
    stars_earned = sum(payment_stars(p.diamonds, p.is_lifetime) for p in payments_rows)
    lifetime_sold = sum(1 for p in payments_rows if p.is_lifetime)

    # Language distribution
    langs = (
        await db.execute(
            select(User.lang, func.count())
            .where(User.lang.is_not(None))
            .group_by(User.lang)
            .order_by(func.count().desc())
        )
    ).all()

    return {
        "total_users": total_users,
        "active_users": active_users,
        "total_conversions": total_conversions,
        "new_today": new_today,
        "new_week": new_week,
        "new_prev_week": new_prev_week,
        "growth_rate": growth_rate,
        "today_conversions": today_conversions,
        "premium_users": premium_users,
        "diamonds_sold": diamonds_sold,
        "stars_earned": stars_earned,
        "lifetime_sold": lifetime_sold,
        "languages": [
            {"lang": lang or "??", "count": count} for lang, count in langs
        ],
    }


@app.get("/api/dashboard/chart")
async def dashboard_chart(
    days: int = Query(7, ge=7, le=365),
    db: AsyncSession = Depends(get_db),
    _=Depends(verify_token),
):
    start_date = date.today() - timedelta(days=days)

    users_data = dict(
        (
            await db.execute(
                select(User.joined_at, func.count())
                .where(User.joined_at >= start_date)
                .group_by(User.joined_at)
            )
        ).all()
    )
    conv_data = dict(
        (
            await db.execute(
                select(Conversion.created_at, func.count())
                .where(Conversion.created_at >= start_date)
                .group_by(Conversion.created_at)
            )
        ).all()
    )

    chart = []
    for i in range(days + 1):
        d = start_date + timedelta(days=i)
        chart.append(
            {
                "date": d.isoformat(),
                "users": users_data.get(d, 0),
                "conversions": conv_data.get(d, 0),
            }
        )
    return chart


# ─── Users ────────────────────────────────────────────────

def _user_dict(u: User) -> dict:
    return {
        "id": u.id,
        "user_id": u.user_id,
        "name": u.name,
        "username": u.username,
        "conversation_count": u.conversation_count or 0,
        "diamonds": u.diamonds or 0,
        "is_premium": bool(u.is_premium),
        "lang": u.lang,
        "joined_at": u.joined_at.isoformat() if u.joined_at else None,
    }


@app.get("/api/users")
async def list_users(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    search: str = Query("", max_length=100),
    sort: str = Query("conversions"),
    db: AsyncSession = Depends(get_db),
    _=Depends(verify_token),
):
    stmt = select(User)
    count_stmt = select(func.count(User.user_id))

    if search:
        like = f"%{search}%"
        flt = User.name.ilike(like) | User.username.ilike(like)
        if search.isdigit():
            flt = flt | (User.user_id == int(search))
        stmt = stmt.where(flt)
        count_stmt = count_stmt.where(flt)

    order_map = {
        "conversions": User.conversation_count.desc(),
        "diamonds": User.diamonds.desc(),
        "joined": User.joined_at.desc(),
        "name": User.name.asc(),
    }
    stmt = stmt.order_by(order_map.get(sort, User.conversation_count.desc()))

    total = (await db.execute(count_stmt)).scalar() or 0
    stmt = stmt.offset((page - 1) * per_page).limit(per_page)
    rows = (await db.execute(stmt)).scalars().all()

    return {
        "users": [_user_dict(u) for u in rows],
        "total": total,
        "page": page,
        "pages": max(1, (total + per_page - 1) // per_page),
    }


@app.get("/api/users/{user_id}")
async def get_user(
    user_id: int,
    db: AsyncSession = Depends(get_db),
    _=Depends(verify_token),
):
    user = (
        await db.execute(select(User).where(User.user_id == user_id))
    ).scalars().first()
    if not user:
        raise HTTPException(404, "User not found")
    return _user_dict(user)


@app.post("/api/users/{user_id}/diamonds")
async def give_diamonds(
    user_id: int,
    body: DiamondRequest,
    db: AsyncSession = Depends(get_db),
    _=Depends(verify_token),
):
    user = (
        await db.execute(select(User).where(User.user_id == user_id))
    ).scalars().first()
    if not user:
        raise HTTPException(404, "User not found")

    user.diamonds = (user.diamonds or 0) + body.count
    await db.commit()
    return {"success": True, "new_balance": user.diamonds}


@app.post("/api/users/{user_id}/premium")
async def toggle_premium(
    user_id: int,
    body: PremiumRequest,
    db: AsyncSession = Depends(get_db),
    _=Depends(verify_token),
):
    user = (
        await db.execute(select(User).where(User.user_id == user_id))
    ).scalars().first()
    if not user:
        raise HTTPException(404, "User not found")

    user.is_premium = body.is_premium
    await db.commit()
    return {"success": True, "is_premium": user.is_premium}


# ─── Top Users ───────────────────────────────────────────

@app.get("/api/top-users")
async def top_users(
    limit: int = Query(10, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
    _=Depends(verify_token),
):
    rows = (
        await db.execute(
            select(User)
            .order_by(User.conversation_count.desc())
            .limit(limit)
        )
    ).scalars().all()
    return [_user_dict(u) for u in rows]


# ─── Export ──────────────────────────────────────────────

@app.get("/api/users/export")
async def export_users(
    token: str = Query(""),
    db: AsyncSession = Depends(get_db),
):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        if payload.get("role") != "admin":
            raise HTTPException(403, "Not admin")
    except Exception:
        raise HTTPException(401, "Invalid token")
    rows = (
        await db.execute(select(User).order_by(User.joined_at.desc()))
    ).scalars().all()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(
        ["user_id", "name", "username", "conversions", "diamonds", "premium", "lang", "joined_at"]
    )
    for u in rows:
        writer.writerow([
            u.user_id, u.name, u.username,
            u.conversation_count or 0, u.diamonds or 0,
            u.is_premium, u.lang,
            u.joined_at.isoformat() if u.joined_at else "",
        ])
    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=users.csv"},
    )


# ─── Broadcast ───────────────────────────────────────────

_broadcasts: dict = {}


async def _do_broadcast(bid: str, user_ids: list[int], text: str, parse_mode: str):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    async with httpx.AsyncClient(timeout=10) as client:
        for uid in user_ids:
            try:
                resp = await client.post(url, json={
                    "chat_id": uid,
                    "text": text,
                    "parse_mode": parse_mode,
                })
                if resp.status_code == 200:
                    _broadcasts[bid]["sent"] += 1
                else:
                    _broadcasts[bid]["failed"] += 1
            except Exception:
                _broadcasts[bid]["failed"] += 1

            done = _broadcasts[bid]["sent"] + _broadcasts[bid]["failed"]
            if done % 25 == 0:
                await asyncio.sleep(1)

    _broadcasts[bid]["status"] = "done"
    _broadcasts[bid]["finished_at"] = datetime.utcnow().isoformat()


@app.post("/api/broadcast")
async def start_broadcast(
    body: BroadcastRequest,
    db: AsyncSession = Depends(get_db),
    _=Depends(verify_token),
):
    if not BOT_TOKEN:
        raise HTTPException(500, "BOT_TOKEN not configured")

    user_ids = (
        await db.execute(select(User.user_id))
    ).scalars().all()

    bid = uuid.uuid4().hex[:8]
    _broadcasts[bid] = {
        "status": "running",
        "total": len(user_ids),
        "sent": 0,
        "failed": 0,
        "text": body.text[:100],
        "started_at": datetime.utcnow().isoformat(),
        "finished_at": None,
    }
    asyncio.create_task(_do_broadcast(bid, user_ids, body.text, body.parse_mode))
    return {"broadcast_id": bid}


@app.get("/api/broadcast/{bid}")
async def broadcast_status(
    bid: str,
    _=Depends(verify_token),
):
    if bid not in _broadcasts:
        raise HTTPException(404, "Broadcast not found")
    return _broadcasts[bid]


@app.get("/api/broadcasts")
async def list_broadcasts(_=Depends(verify_token)):
    return [
        {"id": k, **v} for k, v in sorted(
            _broadcasts.items(),
            key=lambda x: x[1].get("started_at", ""),
            reverse=True,
        )
    ]


# ─── Revenue ────────────────────────────────────────────

@app.get("/api/revenue")
async def revenue(
    db: AsyncSession = Depends(get_db),
    _=Depends(verify_token),
):
    total_payments = (
        await db.execute(select(func.count(Payment.id)))
    ).scalar() or 0
    payments_rows = (await db.execute(select(Payment.diamonds, Payment.is_lifetime))).all()
    diamonds_sold = sum(p.diamonds for p in payments_rows if not p.is_lifetime)
    stars_earned = sum(payment_stars(p.diamonds, p.is_lifetime) for p in payments_rows)
    lifetime_sold = sum(1 for p in payments_rows if p.is_lifetime)
    unique_buyers = (
        await db.execute(select(func.count(distinct(Payment.user_id))))
    ).scalar() or 0

    daily = (
        await db.execute(
            select(Payment.created_at, func.count(), func.coalesce(func.sum(Payment.diamonds), 0))
            .group_by(Payment.created_at)
            .order_by(Payment.created_at.desc())
            .limit(30)
        )
    ).all()

    return {
        "total_payments": total_payments,
        "diamonds_sold": diamonds_sold,
        "stars_earned": stars_earned,
        "lifetime_sold": lifetime_sold,
        "unique_buyers": unique_buyers,
        "daily": [
            {"date": d.isoformat() if d else "", "count": c, "diamonds": dia}
            for d, c, dia in daily
        ],
    }


# ─── Payments ────────────────────────────────────────────

@app.get("/api/payments")
async def list_payments(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    type: str = Query("all"),
    db: AsyncSession = Depends(get_db),
    _=Depends(verify_token),
):
    stmt = select(Payment, User).join(User, User.id == Payment.user_id)
    count_stmt = select(func.count(Payment.id))
    if type == "diamond":
        stmt = stmt.where(Payment.is_lifetime == False)
        count_stmt = count_stmt.where(Payment.is_lifetime == False)
    elif type == "lifetime":
        stmt = stmt.where(Payment.is_lifetime == True)
        count_stmt = count_stmt.where(Payment.is_lifetime == True)
    stmt = stmt.order_by(Payment.created_at.desc(), Payment.id.desc())
    total = (await db.execute(count_stmt)).scalar() or 0
    rows = (await db.execute(stmt.offset((page - 1) * per_page).limit(per_page))).all()
    return {
        "payments": [
            {
                "id": p.id,
                "user_id": u.user_id,
                "user_name": u.name,
                "username": u.username,
                "diamonds": p.diamonds,
                "stars": payment_stars(p.diamonds, p.is_lifetime),
                "is_lifetime": p.is_lifetime,
                "created_at": p.created_at.isoformat() if p.created_at else None,
            }
            for p, u in rows
        ],
        "total": total,
        "pages": max(1, (total + per_page - 1) // per_page),
    }


# ─── Conversions ──────────────────────────────────────────

@app.get("/api/conversions")
async def list_conversions(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    filter: str = Query("all"),
    db: AsyncSession = Depends(get_db),
    _=Depends(verify_token),
):
    stmt = select(Conversion, User).join(User, User.user_id == Conversion.user_id)
    count_stmt = select(func.count(Conversion.id))
    if filter == "premium":
        stmt = stmt.where(Conversion.is_premium == True)
        count_stmt = count_stmt.where(Conversion.is_premium == True)
    elif filter == "free":
        stmt = stmt.where(Conversion.is_premium == False)
        count_stmt = count_stmt.where(Conversion.is_premium == False)
    elif filter == "youtube":
        stmt = stmt.where(Conversion.type == "youtube")
        count_stmt = count_stmt.where(Conversion.type == "youtube")
    elif filter == "video":
        stmt = stmt.where((Conversion.type == "video") | (Conversion.type == None))
        count_stmt = count_stmt.where((Conversion.type == "video") | (Conversion.type == None))
    elif filter == "instagram":
        stmt = stmt.where(Conversion.type == "instagram")
        count_stmt = count_stmt.where(Conversion.type == "instagram")
    elif filter == "tiktok":
        stmt = stmt.where(Conversion.type == "tiktok")
        count_stmt = count_stmt.where(Conversion.type == "tiktok")
    stmt = stmt.order_by(Conversion.created_at.desc(), Conversion.id.desc())
    total = (await db.execute(count_stmt)).scalar() or 0
    rows = (await db.execute(stmt.offset((page - 1) * per_page).limit(per_page))).all()
    return {
        "conversions": [
            {
                "id": c.id,
                "user_id": u.user_id,
                "user_name": u.name,
                "username": u.username,
                "is_premium": c.is_premium,
                "success": c.success,
                "type": c.type or "video",
                "created_at": c.created_at.isoformat() if c.created_at else None,
            }
            for c, u in rows
        ],
        "total": total,
        "pages": max(1, (total + per_page - 1) // per_page),
    }


# ─── Analytics ────────────────────────────────────────────

@app.get("/api/analytics")
async def analytics(
    db: AsyncSession = Depends(get_db),
    _=Depends(verify_token),
):
    today = date.today()
    start_30 = today - timedelta(days=29)
    this_month_start = today.replace(day=1)
    last_month_start = (this_month_start - timedelta(days=1)).replace(day=1)

    total_users = (await db.execute(select(func.count(User.user_id)))).scalar() or 0
    active_users = (await db.execute(select(func.count(distinct(Conversion.user_id))))).scalar() or 0
    paying_users = (await db.execute(select(func.count(distinct(Payment.user_id))))).scalar() or 0
    lifetime_users = (await db.execute(select(func.count(User.user_id)).where(User.is_premium == True))).scalar() or 0
    premium_conv = (await db.execute(select(func.count(Conversion.id)).where(Conversion.is_premium == True))).scalar() or 0
    total_conv = (await db.execute(select(func.count(Conversion.id)))).scalar() or 0

    daily_conv = dict((await db.execute(
        select(Conversion.created_at, func.count()).where(Conversion.created_at >= start_30).group_by(Conversion.created_at)
    )).all())
    daily_users = dict((await db.execute(
        select(User.joined_at, func.count()).where(User.joined_at >= start_30).group_by(User.joined_at)
    )).all())
    daily = [{"date": (start_30 + timedelta(days=i)).isoformat(), "conversions": daily_conv.get(start_30 + timedelta(days=i), 0), "users": daily_users.get(start_30 + timedelta(days=i), 0)} for i in range(30)]

    this_month_users = (await db.execute(select(func.count(User.user_id)).where(User.joined_at >= this_month_start))).scalar() or 0
    last_month_users = (await db.execute(select(func.count(User.user_id)).where(User.joined_at >= last_month_start, User.joined_at < this_month_start))).scalar() or 0
    this_month_conv = (await db.execute(select(func.count(Conversion.id)).where(Conversion.created_at >= this_month_start))).scalar() or 0
    last_month_conv = (await db.execute(select(func.count(Conversion.id)).where(Conversion.created_at >= last_month_start, Conversion.created_at < this_month_start))).scalar() or 0

    return {
        "funnel": [
            {"label": "Total Users", "value": total_users, "color": "#3b82f6", "pct": 100},
            {"label": "Active Users", "value": active_users, "color": "#8b5cf6", "pct": round(active_users / max(total_users, 1) * 100, 1)},
            {"label": "Paying Users", "value": paying_users, "color": "#f59e0b", "pct": round(paying_users / max(total_users, 1) * 100, 1)},
            {"label": "Lifetime Members", "value": lifetime_users, "color": "#10b981", "pct": round(lifetime_users / max(total_users, 1) * 100, 1)},
        ],
        "daily": daily,
        "premium_ratio": round(premium_conv / max(total_conv, 1) * 100, 1),
        "month": {
            "this": {"users": this_month_users, "conversions": this_month_conv},
            "last": {"users": last_month_users, "conversions": last_month_conv},
        },
    }


# ─── Settings ─────────────────────────────────────────────

SETTINGS_FILE = Path(__file__).resolve().parent.parent / "bot_settings.json"
DEFAULT_SETTINGS = {
    "daily_limit": 5,
    "max_file_size_mb": 25,
    "max_queue_size": 50,
    "max_concurrent": 5,
    "lifetime_stars": 200,
    "diamond_prices": {"1": 2, "3": 5, "5": 8, "10": 15, "20": 28, "50": 70},
}

def read_settings() -> dict:
    if SETTINGS_FILE.exists():
        try:
            return {**DEFAULT_SETTINGS, **json.loads(SETTINGS_FILE.read_text())}
        except Exception:
            pass
    return DEFAULT_SETTINGS.copy()

def write_settings(data: dict):
    SETTINGS_FILE.write_text(json.dumps(data, indent=2))

@app.get("/api/settings")
async def get_settings(_=Depends(verify_token)):
    return read_settings()

@app.post("/api/settings")
async def update_settings(body: dict, _=Depends(verify_token)):
    current = read_settings()
    current.update({k: v for k, v in body.items() if k in DEFAULT_SETTINGS})
    write_settings(current)
    return {"success": True, "settings": current}


# ─── Static Files (Production) ────────────────────────────

if STATIC_DIR.exists():
    app.mount("/assets", StaticFiles(directory=STATIC_DIR / "assets"), name="assets")

    @app.get("/{full_path:path}")
    async def serve_spa(request: Request, full_path: str):
        file_path = STATIC_DIR / full_path
        if file_path.exists() and file_path.is_file():
            return FileResponse(file_path)
        return FileResponse(STATIC_DIR / "index.html")
