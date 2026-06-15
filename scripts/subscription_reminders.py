"""Send a one-time reminder to monthly subscribers whose plan is about to
expire in the next 3 days.

Idempotent: each user is reminded at most once per subscription cycle. The
flag (`subscription_reminded_at`) is cleared by extend_subscription() so a
renewed plan can be reminded again later.

Run via cron (daily, e.g. 10:00 server time):

    0 10 * * * cd /path/to/bot && env/bin/python -m scripts.subscription_reminders
"""

import argparse
import asyncio
import logging
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.client.telegram import TelegramAPIServer
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramAPIError, TelegramRetryAfter
from sqlalchemy import and_, select, update
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from config import settings
from database.models import User
from utils.i18n import i18n

REMINDER_WINDOW_DAYS = 3
RATE_LIMIT_SLEEP = 0.05


async def run(dry_run: bool):
    engine = create_async_engine(settings.DATABASE_URL, echo=False)
    Session = async_sessionmaker(engine, expire_on_commit=False)

    today = date.today()
    window_end = today + timedelta(days=REMINDER_WINDOW_DAYS)

    async with Session() as session:
        stmt = (
            select(User)
            .where(
                and_(
                    User.subscription_until.is_not(None),
                    User.subscription_until >= today,
                    User.subscription_until <= window_end,
                    # Lifetime users never need monthly reminders
                    User.is_premium == False,  # noqa: E712
                    # Already reminded for this cycle?
                    (User.subscription_reminded_at.is_(None))
                    | (User.subscription_reminded_at < User.subscription_until - timedelta(days=REMINDER_WINDOW_DAYS)),
                    User.user_id != settings.ADMIN_ID,
                )
            )
            .order_by(User.subscription_until.asc())
        )
        result = await session.execute(stmt)
        targets = list(result.scalars().all())

        print(f"Subscription reminders: {len(targets)} users in next {REMINDER_WINDOW_DAYS} days")

        if dry_run:
            for u in targets:
                print(f"  {u.user_id:>12}  {u.lang or 'en':<3}  expires: {u.subscription_until}")
            print("\n(dry-run — nothing sent)")
            await engine.dispose()
            return

        local_server = TelegramAPIServer.from_base("http://localhost:8081")
        session_http = AiohttpSession(api=local_server, timeout=60)
        bot = Bot(
            token=settings.BOT_TOKEN,
            session=session_http,
            default=DefaultBotProperties(parse_mode=ParseMode.HTML),
        )

        sent, failed, blocked = 0, 0, 0
        try:
            for user in targets:
                text = i18n.get_text("subscription-renewal-reminder", user.lang or "en").format(
                    until=user.subscription_until.strftime("%d %b %Y"),
                )
                try:
                    await bot.send_message(user.user_id, text)
                    sent += 1
                    await session.execute(
                        update(User)
                        .where(User.user_id == user.user_id)
                        .values(subscription_reminded_at=today)
                    )
                    await session.commit()
                except TelegramRetryAfter as e:
                    logging.warning(f"Rate-limited, sleeping {e.retry_after}s")
                    await asyncio.sleep(e.retry_after)
                    continue
                except TelegramAPIError as e:
                    err = str(e).lower()
                    if "blocked" in err or "deactivated" in err or "chat not found" in err:
                        blocked += 1
                    else:
                        failed += 1
                        logging.warning(f"Reminder failed for {user.user_id}: {e}")
                await asyncio.sleep(RATE_LIMIT_SLEEP)
        finally:
            await bot.session.close()

        print(f"\n✅ Sent: {sent}  ⛔ blocked/dead: {blocked}  ❌ other: {failed}")

    await engine.dispose()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    asyncio.run(run(args.dry_run))


if __name__ == "__main__":
    main()
