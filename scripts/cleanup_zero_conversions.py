import asyncio
import argparse
from typing import Optional

from sqlalchemy import delete, select

from config import settings
from database.session import AsyncSessionLocal
from database.models import User


async def cleanup_zero_conversions(include_admin: bool = False, dry_run: bool = False) -> tuple[int, list[int]]:
    async with AsyncSessionLocal() as session:
        stmt = select(User.user_id).where(User.conversation_count == 0)
        if not include_admin:
            stmt = stmt.where(User.user_id != settings.ADMIN_ID)

        result = await session.execute(stmt)
        user_ids = [row[0] for row in result.all()]

        if dry_run or not user_ids:
            return len(user_ids), user_ids

        del_stmt = delete(User).where(User.user_id.in_(user_ids))
        await session.execute(del_stmt)
        await session.commit()
        return len(user_ids), user_ids


async def amain(args):
    count, user_ids = await cleanup_zero_conversions(
        include_admin=args.include_admin,
        dry_run=args.dry_run,
    )

    if args.dry_run:
        print(f"[DRY-RUN] Users with 0 conversions that would be deleted: {count}")
    else:
        print(f"Deleted users with 0 conversions: {count}")

    if args.verbose and user_ids:
        print("User IDs:", ", ".join(str(uid) for uid in user_ids))


def parse_args():
    parser = argparse.ArgumentParser(description="Delete users with 0 conversions from the database.")
    parser.add_argument(
        "--include-admin",
        action="store_true",
        help="Also include ADMIN_ID in deletion if they have 0 conversions (default: skip admin)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Do not delete anything; just print how many users would be deleted",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Print the list of user_ids affected",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    asyncio.run(amain(args))


if __name__ == "__main__":
    main()


