"""Re-engagement broadcast for dormant users.

Targets users who:
  - have diamonds in the bank (something tangible to come back FOR)
  - haven't been active in N days
  - haven't been re-engaged in the last 30 days (so we don't spam)

Run from the project root:

    python3 -m scripts.reengage --days 7 --dry-run
    python3 -m scripts.reengage --days 7        # actually sends

The bot's local Telegram API server is used so this works whether or not
the bot process is running.
"""

import argparse
import asyncio
import logging
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.client.telegram import TelegramAPIServer
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramAPIError, TelegramRetryAfter
from sqlalchemy import and_, func, select, update
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from config import settings
from database.models import User
from utils.i18n import i18n

REENGAGE_COOLDOWN_DAYS = 30
RATE_LIMIT_SLEEP = 0.05  # ~20 messages/sec, well under Telegram's 30/sec cap


def _build_text(user: User) -> str:
    lang = user.lang or "en"
    return i18n.get_text("reengage-message", lang).format(
        diamonds=user.diamonds or 0,
        name=user.name or "👋",
    )


async def find_targets(session, inactive_days: int):
    cutoff = datetime.utcnow() - timedelta(days=inactive_days)
    cooldown = date.today() - timedelta(days=REENGAGE_COOLDOWN_DAYS)

    stmt = (
        select(User)
        .where(
            and_(
                func.coalesce(User.diamonds, 0) > 0,
                User.is_premium == False,  # noqa: E712 — lifetime users don't need diamonds
                User.last_active.is_not(None),
                User.last_active < cutoff,
                # Either never re-engaged, or last re-engaged > cooldown
                (User.reengaged_at.is_(None)) | (User.reengaged_at < cooldown),
                User.blocked_at.is_(None),
                User.user_id != settings.ADMIN_ID,
            )
        )
        .order_by(User.last_active.asc())
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def run(inactive_days: int, dry_run: bool, limit: int | None):
    engine = create_async_engine(settings.DATABASE_URL, echo=False)
    Session = async_sessionmaker(engine, expire_on_commit=False)

    async with Session() as session:
        targets = await find_targets(session, inactive_days)
        if limit:
            targets = targets[:limit]

        print(
            f"Re-engagement targets: {len(targets)} users "
            f"(inactive ≥ {inactive_days}d, diamonds > 0, cooldown {REENGAGE_COOLDOWN_DAYS}d)"
        )

        if dry_run:
            for user in targets[:20]:
                last = user.last_active.strftime("%Y-%m-%d") if user.last_active else "?"
                print(
                    f"  {user.user_id:>12}  {user.lang or 'en':<3}  💎 {user.diamonds:>3}  "
                    f"last_active: {last}  name: {(user.name or '')[:25]}"
                )
            if len(targets) > 20:
                print(f"  … and {len(targets) - 20} more")
            print("\n(dry-run — nothing sent)")
            await engine.dispose()
            return

        # Send for real.
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
                text = _build_text(user)
                try:
                    await bot.send_message(user.user_id, text)
                    sent += 1
                    await session.execute(
                        update(User)
                        .where(User.user_id == user.user_id)
                        .values(reengaged_at=date.today())
                    )
                    # Commit per-user so a mid-run crash doesn't re-spam those
                    # we already messaged.
                    await session.commit()
                except TelegramRetryAfter as e:
                    logging.warning(f"Rate-limited, sleeping {e.retry_after}s")
                    await asyncio.sleep(e.retry_after)
                    continue
                except TelegramAPIError as e:
                    err = str(e).lower()
                    if "blocked" in err or "deactivated" in err or "chat not found" in err:
                        blocked += 1
                        # Persist the block flag so we stop hitting them on
                        # every broadcast/stats query going forward
                        await session.execute(
                            update(User)
                            .where(User.user_id == user.user_id)
                            .values(blocked_at=datetime.utcnow())
                        )
                        await session.commit()
                    else:
                        failed += 1
                        logging.warning(f"Send failed for {user.user_id}: {e}")
                await asyncio.sleep(RATE_LIMIT_SLEEP)
        finally:
            await bot.session.close()

        print(f"\n✅ Sent: {sent}  ⛔ blocked/dead: {blocked}  ❌ other failures: {failed}")

    await engine.dispose()


def main():
    parser = argparse.ArgumentParser(description="Send re-engagement push to dormant users.")
    parser.add_argument("--days", type=int, default=7, help="Inactive threshold in days (default 7)")
    parser.add_argument("--dry-run", action="store_true", help="List targets, don't send")
    parser.add_argument("--limit", type=int, help="Cap the number of users (testing)")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    asyncio.run(run(args.days, args.dry_run, args.limit))


if __name__ == "__main__":
    main()
