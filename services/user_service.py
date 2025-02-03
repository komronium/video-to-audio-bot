from datetime import date
from aiogram import Bot
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import func, select

from config import settings
from database.models import User
from utils.notification import notify_group


class UserService:

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_user(self, user_id: int):
        stmt = select(User).where(User.user_id == user_id)
        result = await self.db.execute(stmt)
        return result.scalars().first()

    async def get_all_users(self, exclude_admin=False):
        stmt = select(User)
        if exclude_admin:
            stmt = stmt.where(User.user_id != settings.ADMIN_ID)

        result = await self.db.execute(stmt)
        return result.scalars().all()

    async def add_user(self, user_id: int, username: str, name: str, bot: Bot):
        user = User(user_id=user_id, username=username, name=name)
        self.db.add(user)
        await self.db.commit()
        await self.db.refresh(user)
        await notify_group(bot, user)
        return user

    async def is_user_exists(self, user_id: int):
        stmt = select(User).where(User.user_id == user_id)
        result = await self.db.execute(stmt)
        return result.scalars().first() is not None

    async def add_conversation(self, user_id: int):
       user = await self.get_user(user_id)
       if user:
           user.conversation_count += 1
           await self.db.commit()

    async def total_users(self, exclude_admin=False):
        stmt = select(func.count(User.user_id))
        if exclude_admin:
            stmt = stmt.where(User.user_id != settings.ADMIN_ID)

        result = await self.db.execute(stmt)
        return result.scalar()

    async def total_active_users(self):
        stmt = select(func.count(User.user_id)).where(User.conversation_count > 0)
        result = await self.db.execute(stmt)
        return result.scalar()

    async def total_conversations(self):
        stmt = select(func.sum(User.conversation_count))
        result = await self.db.execute(stmt)
        return result.scalar() or 0

    async def users_joined_today(self):
        today = date.today()
        stmt = select(func.count(User.user_id)).where(User.joined_at == today)
        result = await self.db.execute(stmt)
        return result.scalar()

    async def get_stats(self):
        return {
            "total_users": await self.total_users(),
            "total_active_users": await self.total_active_users(),
            "total_conversations": await self.total_conversations(),
            "users_joined_today": await self.users_joined_today(),
        }

    async def get_top_users(self, limit=10):
        stmt = (
            select(User)
            .order_by(User.conversation_count.desc())
            .limit(limit)
        )
        result = await self.db.execute(stmt)
        return result.scalars().all()
