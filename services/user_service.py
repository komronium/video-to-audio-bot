import secrets
from datetime import date

from aiogram import Bot
from sqlalchemy import func, select, distinct
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from config import settings
from database.models import Conversion, Payment, Referral, User
from utils.notification import notify_group, notify_milestone


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

    async def add_user(
        self, user_id: int, username: str, name: str, lang: str, bot: Bot
    ):
        try:
            user = User(user_id=user_id, username=username, name=name, lang=lang)
            self.db.add(user)
            await self.db.commit()
            await self.db.refresh(user)
            await notify_group(bot, user, lang, self.db)
            # Milestone facts after user created
            total = await self.total_users()
            await notify_milestone(bot, total)
            return user
        except IntegrityError:
            await self.db.rollback()
            return await self.get_user(user_id)

    async def is_user_exists(self, user_id: int):
        stmt = select(User).where(User.user_id == user_id)
        result = await self.db.execute(stmt)
        return result.scalars().first() is not None

    async def add_conversation(self, user_id: int, conv_type: str = "video"):
        user = await self.get_user(user_id)
        conversion = Conversion(user_id=user_id, type=conv_type)
        if user.is_premium:
            conversion.is_premium = True

        user.conversation_count = (user.conversation_count or 0) + 1
        self.db.add(conversion)
        await self.db.commit()

    async def get_conversion_count(self, user_id: int):
        stmt = select(func.count(Conversion.id)).where(Conversion.user_id == user_id)
        result = await self.db.execute(stmt)
        return result.scalar_one()

    async def total_users(self, exclude_admin=False):
        stmt = select(func.count(User.user_id))
        if exclude_admin:
            stmt = stmt.where(User.user_id != settings.ADMIN_ID)

        result = await self.db.execute(stmt)
        return result.scalar()

    async def total_active_users(self):
        stmt = (
            select(func.count(distinct(User.user_id)))
            .join(Conversion, User.user_id == Conversion.user_id)
        )
        result = await self.db.execute(stmt)
        return result.scalar()

    async def total_conversations(self):
        stmt = select(func.count(Conversion.id)).where(Conversion.success == True)
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
        stmt = select(User).order_by(User.conversation_count.desc()).limit(limit)
        result = await self.db.execute(stmt)
        return result.scalars().all()

    async def get_user_rank(self, user_id: int):
        """Return 1-based rank by conversation_count. None if user not found."""
        user = await self.get_user(user_id)
        if not user:
            return None

        higher_stmt = select(func.count(User.user_id)).where(
            User.conversation_count > user.conversation_count
        )
        result = await self.db.execute(higher_stmt)
        higher = result.scalar() or 0
        return higher + 1

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

    async def add_diamonds(self, user_id: int, count: int, record_payment: bool = True):
        user = await self.get_user(user_id)
        if user:
            user.diamonds = (user.diamonds or 0) + count
            if record_payment:
                payment = Payment(user_id=user.id, diamonds=count, is_lifetime=False)
                self.db.add(payment)
            await self.db.commit()

    async def set_lifetime(self, user_id: int):
        user = await self.get_user(user_id)
        if user:
            user.diamonds = 99999
            user.is_premium = True
            payment = Payment(user_id=user.id, diamonds=0, is_lifetime=True)
            self.db.add(payment)
            await self.db.commit()

    async def is_lifetime(self, user_id: int) -> bool:
        user = await self.get_user(user_id)
        return user and user.diamonds >= 99999

    async def get_lang(self, user_id: int):
        user = await self.get_user(user_id)
        if not user:
            return "en"
        return user.lang or "en"

    async def set_lang(self, user_id: int, lang: str):
        user = await self.get_user(user_id)
        if not user:
            return
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

    async def get_top_language(self):
        """Return most popular language."""
        stmt = (
            select(User.lang, func.count(User.user_id).label("count"))
            .where(User.lang.is_not(None))
            .group_by(User.lang)
            .order_by(func.count(User.user_id).desc())
            .limit(1)
        )
        result = await self.db.execute(stmt)
        row = result.first()
        return row[0] if row else None

    async def generate_referral_code(self, user_id: int) -> str:
        user = await self.get_user(user_id)
        if not user:
            return None
        if user.referral_code:
            return user.referral_code
        while True:
            code = secrets.token_urlsafe(8)[:10].upper()
            stmt = select(User).where(User.referral_code == code)
            result = await self.db.execute(stmt)
            if not result.scalars().first():
                user.referral_code = code
                await self.db.commit()
                return code

    async def get_user_by_referral_code(self, code: str):
        stmt = select(User).where(User.referral_code == code)
        result = await self.db.execute(stmt)
        return result.scalars().first()

    async def apply_referral(self, user_id: int, referral_code: str) -> bool:
        user = await self.get_user(user_id)
        if not user or user.referral_code_id:
            return False
        inviter = await self.get_user_by_referral_code(referral_code)
        if not inviter or inviter.id == user.id:
            return False
        user.referral_code_id = inviter.id
        await self.db.commit()
        return True

    async def check_referral_reward(self, user_id: int) -> tuple[bool, int | None]:
        user = await self.get_user(user_id)
        if not user or user.referral_rewarded or not user.referral_code_id:
            return False, None
        return True, user.referral_code_id

    async def grant_referral_reward(self, user_id: int):
        user = await self.get_user(user_id)
        if not user or user.referral_rewarded:
            return False
        inviter_id = user.referral_code_id
        if not inviter_id:
            return False
        inviter = await self.db.get(User, inviter_id)
        if inviter:
            await self.add_diamonds(inviter.user_id, 2, record_payment=False)
        await self.add_diamonds(user_id, 1, record_payment=False)
        user.referral_rewarded = True
        referral = Referral(inviter_id=inviter_id, invited_id=user.id)
        self.db.add(referral)
        await self.db.commit()
        return True

    async def check_milestone_rewards(self, user_id: int) -> int:
        user = await self.get_user(user_id)
        if not user:
            return 0
        count = user.conversation_count or 0
        milestones = {50: 5, 100: 10, 200: 20, 500: 50}
        reward = 0
        for threshold, bonus in milestones.items():
            if count == threshold:
                reward = bonus
                break
        return reward

    async def grant_milestone_reward(self, user_id: int, diamonds: int):
        await self.add_diamonds(user_id, diamonds, record_payment=False)
