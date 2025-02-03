import asyncio
from datetime import date
from sqlalchemy import Column, Integer, String, Date
from sqlalchemy.orm import declarative_base

from .session import engine

Base = declarative_base()


class User(Base):
    __tablename__ = 'users'

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, unique=True, nullable=False)
    name = Column(String)
    username = Column(String, nullable=True)
    conversation_count = Column(Integer, default=0)
    joined_at = Column(Date, default=date.today)


async def create_tables():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


asyncio.run(create_tables())
