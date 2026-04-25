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

    async def get_user(self, user_id: int) -> User | None:
        result = await self.db.execute(select(User).where(User.user_id == user_id))
        return result.scalars().first()

    async def get_all_users(self, exclude_admin: bool = False) -> list[User]:
        stmt = select(User)
        if exclude_admin:
            stmt = stmt.where(User.user_id != settings.ADMIN_ID)
        result = await self.db.execute(stmt)
        return result.scalars().all()

    async def add_user(self, user_id: int, username: str, name: str, lang: str, bot: Bot) -> User:
        try:
            user = User(user_id=user_id, username=username, name=name, lang=lang)
            self.db.add(user)
            await self.db.commit()
            await self.db.refresh(user)
            await notify_group(bot, user, lang, self.db)
            total = await self.total_users()
            await notify_milestone(bot, total)
            return user
        except IntegrityError:
            await self.db.rollback()
            return await self.get_user(user_id)

    async def is_user_exists(self, user_id: int) -> bool:
        result = await self.db.execute(select(User.id).where(User.user_id == user_id))
        return result.first() is not None

    async def add_conversation(self, user_id: int, conv_type: str = "video"):
        user = await self.get_user(user_id)
        if not user:
            return
        conversion = Conversion(user_id=user.id, type=conv_type)
        if user.is_premium:
            conversion.is_premium = True
        user.conversation_count = (user.conversation_count or 0) + 1
        self.db.add(conversion)
        await self.db.commit()

    async def get_conversion_count(self, user_id: int) -> int:
        user = await self.get_user(user_id)
        if not user:
            return 0
        result = await self.db.execute(
            select(func.count(Conversion.id)).where(Conversion.user_id == user.id)
        )
        return result.scalar_one()

    async def total_users(self, exclude_admin: bool = False) -> int:
        stmt = select(func.count(User.user_id))
        if exclude_admin:
            stmt = stmt.where(User.user_id != settings.ADMIN_ID)
        result = await self.db.execute(stmt)
        return result.scalar() or 0

    async def total_active_users(self) -> int:
        stmt = (
            select(func.count(distinct(User.user_id)))
            .join(Conversion, User.id == Conversion.user_id)
        )
        result = await self.db.execute(stmt)
        return result.scalar() or 0

    async def total_conversations(self) -> int:
        result = await self.db.execute(
            select(func.count(Conversion.id)).where(Conversion.success == True)  # noqa: E712
        )
        return result.scalar() or 0

    async def users_joined_today(self) -> int:
        result = await self.db.execute(
            select(func.count(User.user_id)).where(User.joined_at == date.today())
        )
        return result.scalar() or 0

    async def get_stats(self) -> dict:
        return {
            "total_users": await self.total_users(),
            "total_active_users": await self.total_active_users(),
            "total_conversations": await self.total_conversations(),
            "users_joined_today": await self.users_joined_today(),
        }

    async def get_top_users(self, limit: int = 10) -> list[User]:
        result = await self.db.execute(
            select(User).order_by(User.conversation_count.desc()).limit(limit)
        )
        return result.scalars().all()

    async def get_user_rank(self, user_id: int) -> int | None:
        user = await self.get_user(user_id)
        if not user:
            return None
        result = await self.db.execute(
            select(func.count(User.user_id)).where(
                User.conversation_count > user.conversation_count
            )
        )
        return (result.scalar() or 0) + 1

    async def get_user_diamonds(self, user_id: int) -> int:
        user = await self.get_user(user_id)
        return user.diamonds or 0 if user else 0

    async def use_diamond(self, user_id: int) -> bool:
        user = await self.get_user(user_id)
        if user and user.diamonds > 0:
            user.diamonds -= 1
            await self.db.commit()
            return True
        return False

    async def add_diamonds(self, user_id: int, count: int, record_payment: bool = True):
        user = await self.get_user(user_id)
        if not user:
            return
        user.diamonds = (user.diamonds or 0) + count
        if record_payment:
            self.db.add(Payment(user_id=user.id, diamonds=count, is_lifetime=False))
        await self.db.commit()

    async def set_lifetime(self, user_id: int):
        user = await self.get_user(user_id)
        if not user:
            return
        user.diamonds = 99999
        user.is_premium = True
        self.db.add(Payment(user_id=user.id, diamonds=0, is_lifetime=True))
        await self.db.commit()

    async def is_lifetime(self, user_id: int) -> bool:
        user = await self.get_user(user_id)
        return bool(user and user.diamonds >= 99999)

    async def get_lang(self, user_id: int) -> str:
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

    async def get_langs(self) -> dict[str, int]:
        users = await self.get_all_users()
        langs: dict[str, int] = {}
        for user in users:
            key = user.lang or "unknown"
            langs[key] = langs.get(key, 0) + 1
        return langs

    async def get_top_language(self) -> str | None:
        result = await self.db.execute(
            select(User.lang, func.count(User.user_id).label("count"))
            .where(User.lang.is_not(None))
            .group_by(User.lang)
            .order_by(func.count(User.user_id).desc())
            .limit(1)
        )
        row = result.first()
        return row[0] if row else None

    async def generate_referral_code(self, user_id: int) -> str | None:
        user = await self.get_user(user_id)
        if not user:
            return None
        if user.referral_code:
            return user.referral_code
        while True:
            code = secrets.token_urlsafe(8)[:10].upper()
            exists = await self.db.execute(select(User.id).where(User.referral_code == code))
            if not exists.first():
                user.referral_code = code
                await self.db.commit()
                return code

    async def get_user_by_referral_code(self, code: str) -> User | None:
        result = await self.db.execute(select(User).where(User.referral_code == code))
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

    async def grant_referral_reward(self, user_id: int) -> tuple[bool, int | None]:
        user = await self.get_user(user_id)
        if not user or user.referral_rewarded or not user.referral_code_id:
            return False, None
        inviter = await self.db.get(User, user.referral_code_id)
        if not inviter:
            return False, None
        inviter.diamonds = (inviter.diamonds or 0) + 2
        user.diamonds = (user.diamonds or 0) + 1
        user.referral_rewarded = True
        self.db.add(Referral(inviter_id=inviter.id, invited_id=user.id))
        await self.db.commit()
        return True, inviter.user_id

    async def check_milestone_rewards(self, user_id: int) -> int:
        user = await self.get_user(user_id)
        if not user:
            return 0
        count = user.conversation_count or 0
        milestones = {50: 5, 100: 10, 200: 20, 500: 50}
        return milestones.get(count, 0)

    async def grant_milestone_reward(self, user_id: int, diamonds: int):
        await self.add_diamonds(user_id, diamonds, record_payment=False)
