"""Admin Dashboard API for Video-to-Audio Bot."""

import os
import jwt
from datetime import datetime, timedelta, date
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

from fastapi import FastAPI, Depends, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
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


# ─── Dashboard ────────────────────────────────────────────

@app.get("/api/dashboard")
async def dashboard(
    db: AsyncSession = Depends(get_db),
    _=Depends(verify_token),
):
    today = date.today()
    week_ago = today - timedelta(days=7)

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
    premium_users = (
        await db.execute(
            select(func.count(User.user_id)).where(User.is_premium == True)
        )
    ).scalar() or 0

    # Revenue
    diamonds_sold = (
        await db.execute(
            select(func.coalesce(func.sum(Payment.diamonds), 0))
        )
    ).scalar() or 0
    lifetime_sold = (
        await db.execute(
            select(func.count()).where(Payment.is_lifetime == True)
        )
    ).scalar() or 0

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
        "premium_users": premium_users,
        "diamonds_sold": diamonds_sold,
        "lifetime_sold": lifetime_sold,
        "languages": [
            {"lang": lang or "??", "count": count} for lang, count in langs
        ],
    }


@app.get("/api/dashboard/chart")
async def dashboard_chart(
    days: int = Query(30, ge=7, le=90),
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


# ─── Static Files (Production) ────────────────────────────

if STATIC_DIR.exists():
    app.mount("/assets", StaticFiles(directory=STATIC_DIR / "assets"), name="assets")

    @app.get("/{full_path:path}")
    async def serve_spa(request: Request, full_path: str):
        file_path = STATIC_DIR / full_path
        if file_path.exists() and file_path.is_file():
            return FileResponse(file_path)
        return FileResponse(STATIC_DIR / "index.html")
