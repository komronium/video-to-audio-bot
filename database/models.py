from datetime import date

from sqlalchemy import Boolean, Column, Date, DateTime, ForeignKey, Integer, String, text
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
    last_active = Column(DateTime, nullable=True, index=True)
    source = Column(String(30), nullable=True, index=True)
    reengaged_at = Column(Date, nullable=True)
    # Monthly Stars-paid subscription. is_premium stays for lifetime (sticky
    # for life), so a user can hold either or both. Active premium =
    # is_premium OR subscription_until >= today.
    subscription_until = Column(Date, nullable=True, index=True)
    subscription_reminded_at = Column(Date, nullable=True)
    # Set when the user blocks the bot (broadcast/reengage detects 403 etc).
    # Auto-cleared on the next interaction — if they unblock and message us
    # again, they're alive. Hard-deletion would orphan their payments and
    # referrals, so we soft-flag instead.
    blocked_at = Column(DateTime, nullable=True, index=True)

    conversions = relationship(
        "Conversion",
        back_populates="user",
        primaryjoin="User.user_id == foreign(Conversion.user_id)",
        viewonly=True,
    )
    payments = relationship("Payment", back_populates="user")
    referrals_made = relationship("Referral", foreign_keys="Referral.inviter_id", back_populates="inviter")

    @property
    def is_active_premium(self) -> bool:
        """Either lifetime or an unexpired monthly subscription unlocks
        unlimited usage. Reads only loaded columns — no DB hit."""
        if self.is_premium:
            return True
        return bool(self.subscription_until and self.subscription_until >= date.today())


class Conversion(Base):
    __tablename__ = "conversions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    # Stores the Telegram user_id (users.user_id), NOT users.id — all existing
    # rows and queries use it this way, so no FK to users.id here.
    user_id = Column(Integer, index=True)
    success = Column(Boolean, default=True)
    is_premium = Column(Boolean, default=False)
    type = Column(String(20), default="video", nullable=True)
    created_at = Column(Date, default=date.today)

    user = relationship(
        "User",
        back_populates="conversions",
        primaryjoin="foreign(Conversion.user_id) == User.user_id",
        viewonly=True,
    )


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
    "ALTER TABLE users ADD COLUMN last_active DATETIME",
    "ALTER TABLE users ADD COLUMN source VARCHAR(30)",
    "ALTER TABLE users ADD COLUMN reengaged_at DATE",
    "ALTER TABLE users ADD COLUMN subscription_until DATE",
    "ALTER TABLE users ADD COLUMN subscription_reminded_at DATE",
    "ALTER TABLE users ADD COLUMN blocked_at DATETIME",
    "CREATE INDEX IF NOT EXISTS ix_users_subscription_until ON users(subscription_until)",
    "CREATE INDEX IF NOT EXISTS ix_users_blocked_at ON users(blocked_at)",
    "CREATE INDEX IF NOT EXISTS ix_conversions_user_id ON conversions(user_id)",
    "CREATE INDEX IF NOT EXISTS ix_conversions_created_at ON conversions(created_at)",
    "CREATE INDEX IF NOT EXISTS ix_users_joined_at ON users(joined_at)",
    "CREATE INDEX IF NOT EXISTS ix_users_last_active ON users(last_active)",
    "CREATE INDEX IF NOT EXISTS ix_users_source ON users(source)",
]


async def create_tables():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        for stmt in _MIGRATIONS:
            try:
                await conn.execute(text(stmt))
            except Exception:
                pass
