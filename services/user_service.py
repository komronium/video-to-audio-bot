import logging
from datetime import date
from aiogram import Bot
from sqlalchemy.exc import IntegrityError
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
        try:
            user = User(user_id=user_id, username=username, name=name)
            self.db.add(user)
            await self.db.commit()
            await self.db.refresh(user)
            await notify_group(bot, user)
            return user
        except IntegrityError:
            await self.db.rollback()
            return await self.get_user(user_id)

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

    async def get_user_diamonds(self, user_id: int) -> int:
        user = await self.get_user(user_id)
        if user:
            return user.diamonds or 0
        return 0

    async def use_diamond(self, user_id: int) -> bool:
        """Diamonddan foydalanish (1 dona - universal)"""
        user = await self.get_user(user_id)
        if user and user.diamonds > 0:
            user.diamonds -= 1
            await self.db.commit()
            return True
        return False

    async def add_diamonds(self, user_id: int, count: int):
        user = await self.get_user(user_id)
        if user:
            user.diamonds = (user.diamonds or 0) + count
            await self.db.commit()

    async def set_lifetime(self, user_id: int):
        user = await self.get_user(user_id)
        if user:
            user.diamonds = 99999
            await self.db.commit()

    async def is_lifetime(self, user_id: int) -> bool:
        user = await self.get_user(user_id)
        logging.warning(f"is_lifetime: {user}, diamonds: {user.diamonds if user else 'None'}, {user and user.diamonds >= 99999}")
        return user and user.diamonds >= 99999

    async def get_lang(self, user_id: int):
        user = await self.get_user(user_id)
        return user.lang

    async def set_lang(self, user_id: int, lang: str):
        user = await self.get_user(user_id)
        user.lang = lang
        await self.db.commit()

    async def get_langs(self):
        users = await self.get_all_users()
        langs = {}

        for user in users:
            lang = user.lang
            if lang not in langs:
                langs[lang] = 1
            else:
                langs[lang] += 1

        return langs
