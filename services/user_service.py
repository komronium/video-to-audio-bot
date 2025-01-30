from datetime import date
from aiogram import Bot
from sqlalchemy.orm import Session
from sqlalchemy import func, text

from database.models import User
from utils.notification import notify_group


class UserService:

    def __init__(self, db: Session):
        self.db = db

    def get_user(self, user_id: int):
        return self.db.query(User).filter(User.user_id == user_id).first()

    async def add_user(self, user_id: int, username: str, name: str, bot: Bot):
        user = User(user_id=user_id, username=username, name=name)
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        await notify_group(bot, user)
        return user

    def is_user_exists(self, user_id: int):
        return self.db.query(User).filter(User.user_id == user_id).first() is not None

    async def add_conversation(self, user_id: int):
        user = self.get_user(user_id)
        if user:
            user.conversation_count += 1
            self.db.commit()

        return None

    def total_users(self):
        return self.db.query(User).count()

    def total_active_users(self):
        return self.db.query(User).filter(User.conversation_count > 0).count()

    def total_conversations(self):
        return self.db.query(func.sum(User.conversation_count)).scalar() or 0

    def users_joined_today(self):
        today = date.today()
        return self.db.query(User).filter(User.joined_at == today).count()

    def get_stats(self):
        return {
            "total_users": self.total_users(),
            "total_active_users": self.total_active_users(),
            "total_conversations": self.total_conversations(),
            "users_joined_today": self.users_joined_today(),
        }

    def get_top_users(self, limit=10):
        return self.db.query(User).order_by(text('-conversation_count')).limit(limit).all()
