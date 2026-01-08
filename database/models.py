import asyncio
from datetime import date

from sqlalchemy import Boolean, Column, Date, ForeignKey, Integer, String
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

    conversions = relationship("Conversion", back_populates="user")
    payments = relationship("Payment", back_populates="user")


class Conversion(Base):
    __tablename__ = "conversions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    success = Column(Boolean, default=True)
    is_premium = Column(Boolean, default=False)
    created_at = Column(Date, default=date.today)

    user = relationship("User", back_populates="conversions")


class Payment(Base):
    __tablename__ = "payments"
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    diamonds = Column(Integer, default=0)  # 💎 sotib olingan diamondlar
    is_lifetime = Column(Boolean, default=False)
    created_at = Column(Date, default=date.today)

    user = relationship("User", back_populates="payments")


async def create_tables():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


asyncio.run(create_tables())
