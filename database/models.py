from datetime import date

from sqlalchemy import Boolean, Column, Date, ForeignKey, Integer, String, text
from sqlalchemy.orm import declarative_base, relationship

from .session import engine

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
    referral_code = Column(String(20), unique=True, nullable=True)
    referral_code_id = Column(Integer, nullable=True)
    referral_rewarded = Column(Boolean, default=False)

    conversions = relationship("Conversion", back_populates="user", foreign_keys="Conversion.user_id")
    payments = relationship("Payment", back_populates="user")
    referrals_made = relationship("Referral", foreign_keys="Referral.inviter_id", back_populates="inviter")


class Conversion(Base):
    __tablename__ = "conversions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    success = Column(Boolean, default=True)
    is_premium = Column(Boolean, default=False)
    type = Column(String(20), default="video", nullable=True)
    created_at = Column(Date, default=date.today)

    user = relationship("User", back_populates="conversions", foreign_keys=[user_id])


class Payment(Base):
    __tablename__ = "payments"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    diamonds = Column(Integer, default=0)
    is_lifetime = Column(Boolean, default=False)
    created_at = Column(Date, default=date.today)

    user = relationship("User", back_populates="payments")


class Referral(Base):
    __tablename__ = "referrals"

    id = Column(Integer, primary_key=True, autoincrement=True)
    inviter_id = Column(Integer, ForeignKey("users.id"))
    invited_id = Column(Integer, ForeignKey("users.id"))
    created_at = Column(Date, default=date.today)

    inviter = relationship("User", foreign_keys=[inviter_id], back_populates="referrals_made")


_MIGRATIONS = [
    "ALTER TABLE conversions ADD COLUMN type VARCHAR DEFAULT 'video'",
    "ALTER TABLE users ADD COLUMN referral_code VARCHAR(20) UNIQUE",
    "ALTER TABLE users ADD COLUMN referral_code_id INTEGER",
    "ALTER TABLE users ADD COLUMN referral_rewarded BOOLEAN DEFAULT 0",
]


async def create_tables():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        for stmt in _MIGRATIONS:
            try:
                await conn.execute(text(stmt))
            except Exception:
                pass
