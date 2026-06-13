import asyncio
import logging
import re
from datetime import datetime

from aiogram import F, Router
from aiogram.exceptions import TelegramAPIError
from aiogram.types import Document, Message
from redis.exceptions import RedisError
from sqlalchemy.ext.asyncio import AsyncSession

from services.job_queue import job_queue
from services.user_service import UserService
from services.workers import fail_job, process_job
from utils.daily_limit import DAILY_LIMIT, get_daily_count, reset_time_str
from utils.i18n import i18n
from utils.upsell import get_buy_more_keyboard

MAX_FILE_SIZE = 50 * 1024 * 1024
MAX_QUEUE_SIZE = 50

# Used only when Redis is down and jobs are processed inline
_fallback_semaphore = asyncio.Semaphore(3)

router = Router()


def _generate_name(message: Message, video) -> str:
    def sanitize(name: str) -> str:
        return re.sub(r"[^a-zA-Z0-9_-]", "", name)

    if message.caption:
        clean = sanitize(message.caption[:25].lower().replace(" ", "_"))
        if clean:
            return clean
    if video.file_name:
        clean = sanitize(video.file_name.rsplit(".", 1)[0].lower().replace(" ", "_"))
        if clean:
            return clean
    return f"audio_{message.from_user.id}_{int(datetime.now().timestamp())}"


@router.message(F.video)
async def video_handler(message: Message, db: AsyncSession, document: Document = None):
    user_service = UserService(db)
    user = await user_service.get_user(message.from_user.id)
    is_new = False
    if not user:
        tg = message.from_user
        user = await user_service.add_user(
            tg.id, tg.username, tg.full_name, tg.language_code or "en", message.bot
        )
        is_new = True
    lang = user.lang or "en"
    is_lifetime = user.is_premium
    user_id = message.from_user.id

    video = message.video if document is None else document

    # Queue checks come before charging so rejections never need a refund
    pending = 0
    redis_ok = True
    try:
        pending = await job_queue.pending_count()
        if pending >= MAX_QUEUE_SIZE:
            await message.reply(i18n.get_text("server-busy", lang))
            return
        if await job_queue.user_has_job(user_id):
            await message.reply(i18n.get_text("queue-wait", lang))
            return
    except RedisError:
        redis_ok = False

    # One diamond covers a large file and/or going over the daily limit —
    # a single video never charges twice.
    is_large = video.file_size > MAX_FILE_SIZE
    current = await get_daily_count(user_id)
    over_limit = current + 1 > DAILY_LIMIT
    charged = 0

    if not is_lifetime and (is_large or over_limit):
        if not await user_service.use_diamond(user_id):
            if is_large:
                size_mb = MAX_FILE_SIZE // (1024 * 1024)
                await message.reply(
                    i18n.get_text("too-large", lang).format(size_mb)
                    + "\n\n"
                    + i18n.get_text("limit-invite-tip", lang),
                    reply_markup=await get_buy_more_keyboard(lang, user_service, user_id, message.bot),
                )
            else:
                await message.answer(
                    i18n.get_text("daily-limit", lang).format(limit=DAILY_LIMIT, time=reset_time_str()),
                    reply_markup=await get_buy_more_keyboard(lang, user_service, user_id, message.bot),
                )
            return
        charged = 1

    # Fold every preamble (first-time welcome, diamond notice) into the single
    # status message instead of sending separate messages.
    prefix = ""
    if is_new:
        prefix += i18n.get_text("first-video", lang) + "\n\n"
    if charged:
        prefix += i18n.get_text("large-used" if is_large else "extra-used", lang) + "\n\n"

    status_msg_id = None
    status_text = prefix + (
        i18n.get_text("queue", lang).format(pending + 1, pending + 1)
        if redis_ok and pending > 0
        else i18n.get_text("downloading", lang)
    )
    try:
        status_msg = await message.reply(status_text)
        status_msg_id = status_msg.message_id
    except TelegramAPIError:
        pass

    job = {
        "type": "video",
        "user_id": user_id,
        "chat_id": message.chat.id,
        "reply_to": message.message_id,
        "file_id": video.file_id,
        "file_name": _generate_name(message, video),
        "lang": lang,
        "charged": charged,
        "is_lifetime": is_lifetime,
        "status_msg_id": status_msg_id,
        "attempts": 0,
        "enqueued_at": int(message.date.timestamp()),
    }

    if redis_ok:
        try:
            await job_queue.enqueue(job)
            return
        except RedisError:
            pass

    # Redis is down: degrade to inline processing so the bot keeps working
    logging.warning(f"Redis unavailable, processing video inline for user {user_id}")
    async with _fallback_semaphore:
        try:
            await process_job(message.bot, job)
        except Exception as e:
            logging.exception(f"Inline video processing failed for user {user_id}")
            await fail_job(message.bot, job, e)


@router.message(F.document.mime_type.startswith("video"))
async def document_handler(message: Message, db: AsyncSession):
    await video_handler(message, db, message.document)
