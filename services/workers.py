import asyncio
import logging
import os

from aiogram import Bot
from aiogram.exceptions import TelegramAPIError, TelegramRetryAfter
from aiogram.types import FSInputFile, ReplyParameters
from redis.exceptions import RedisError

from config import settings
from database.session import get_db
from services.converter import NoAudioError, VideoConverter
from services.job_queue import job_queue
from services.user_service import UserService
from utils.admin_alert import notify_admin
from utils.daily_limit import increment_daily_count
from utils.i18n import i18n
from utils.rewards import check_and_notify_rewards
from utils.upsell import get_bot_username, post_conversion_upsell

MAX_CONCURRENT = 5
MAX_ATTEMPTS = 2

# Root data dir of the local telegram-bot-api server. get_file() may return a
# path relative to <BOT_API_DIR>/<token>/ (non --local mode) or an absolute
# path (--local mode); we normalise to an absolute path either way.
BOT_API_DIR = os.getenv("TELEGRAM_BOT_API_DIR", "/var/lib/telegram-bot-api")

_tasks: list[asyncio.Task] = []


def start_workers(bot: Bot, count: int = MAX_CONCURRENT):
    for n in range(count):
        _tasks.append(
            asyncio.create_task(_worker_loop(bot, n), name=f"conversion-worker-{n}")
        )
    logging.info(f"Started {count} conversion workers")


async def stop_workers():
    for task in _tasks:
        task.cancel()
    await asyncio.gather(*_tasks, return_exceptions=True)
    _tasks.clear()


async def _worker_loop(bot: Bot, n: int):
    while True:
        try:
            reserved = await job_queue.reserve(timeout=5)
        except RedisError:
            logging.warning(f"Worker {n}: Redis unavailable, retrying in 5s")
            await asyncio.sleep(5)
            continue
        if reserved is None:
            continue

        raw, job = reserved
        try:
            if job.get("attempts", 0) >= MAX_ATTEMPTS:
                await fail_job(bot, job, RuntimeError("max attempts exceeded"))
            else:
                await process_job(bot, job)
            await _safe_ack(raw)
        except asyncio.CancelledError:
            # Shutdown mid-job: leave it in jobs:processing so
            # requeue_orphans() picks it up on the next start.
            raise
        except Exception as e:
            await _handle_failure(bot, job, e)
            await _safe_ack(raw)


async def _safe_ack(raw: str):
    try:
        await job_queue.ack(raw)
    except RedisError:
        logging.warning("Could not ack job; it will be requeued on next restart")


async def _handle_failure(bot: Bot, job: dict, exc: Exception):
    logging.error(f"Job failed for user {job.get('user_id')}: {exc}", exc_info=exc)
    job["attempts"] = job.get("attempts", 0) + 1
    if job["attempts"] < MAX_ATTEMPTS:
        try:
            await job_queue.enqueue(job)
            return
        except RedisError:
            pass
    await fail_job(bot, job, exc)


async def fail_job(bot: Bot, job: dict, exc: Exception):
    user_id, chat_id, lang = job["user_id"], job["chat_id"], job.get("lang", "en")
    await _refund(user_id, job.get("charged", 0))
    error_text = i18n.get_text("error-server", lang)
    try:
        if job.get("status_msg_id"):
            await bot.edit_message_text(
                error_text, chat_id=chat_id, message_id=job["status_msg_id"]
            )
        else:
            await bot.send_message(chat_id, error_text)
    except TelegramAPIError:
        pass
    # Dedupe by error type: a recurring failure (e.g. network timeouts to the
    # local Bot API) alerts the admin once per window, not once per user.
    await notify_admin(
        bot,
        f"<b>❌ Conversion job failed</b>\n"
        f"<b>User:</b> <code>{user_id}</code>\n"
        f"<b>Attempts:</b> {job.get('attempts', 0)}\n"
        f"<b>Error:</b> <code>{type(exc).__name__}: {str(exc)[:300]}</code>",
        dedupe_key=f"job-failed:{type(exc).__name__}",
    )


async def _refund(user_id: int, count: int):
    if not count:
        return
    try:
        async with get_db() as db:
            await UserService(db).refund_diamonds(user_id, count)
    except Exception:
        logging.exception(f"Failed to refund {count} diamonds to user {user_id}")


async def process_job(bot: Bot, job: dict):
    user_id, chat_id, lang = job["user_id"], job["chat_id"], job.get("lang", "en")
    status_msg_id = job.get("status_msg_id")
    video_path = None
    audio_path = None

    async def edit_status(text: str):
        if status_msg_id:
            try:
                await bot.edit_message_text(
                    text, chat_id=chat_id, message_id=status_msg_id
                )
            except TelegramAPIError:
                pass

    def reply_params() -> ReplyParameters | None:
        if job.get("reply_to"):
            return ReplyParameters(
                message_id=job["reply_to"], allow_sending_without_reply=True
            )
        return None

    try:
        await edit_status(i18n.get_text("downloading", lang))

        file = await bot.get_file(job["file_id"])
        video_path = file.file_path
        if not os.path.isabs(video_path):
            video_path = os.path.join(BOT_API_DIR, settings.BOT_TOKEN, video_path)

        await edit_status(i18n.get_text("converting", lang))

        try:
            audio_path = await VideoConverter().convert_video_to_audio(
                video_path, f"audios/{job['file_name']}"
            )
        except NoAudioError:
            await edit_status(i18n.get_text("no-audio", lang))
            await _refund(user_id, job.get("charged", 0))
            return

        caption = i18n.get_text("converted-by", lang).format(
            await get_bot_username(bot)
        )

        async with get_db() as db:
            await UserService(db).add_conversation(user_id=user_id)

        await edit_status(i18n.get_text("uploading", lang))
        try:
            await bot.send_chat_action(chat_id, "upload_document")
        except TelegramAPIError:
            pass

        try:
            await bot.send_document(
                chat_id,
                FSInputFile(audio_path),
                caption=caption,
                reply_parameters=reply_params(),
            )
            await bot.send_voice(
                chat_id, FSInputFile(audio_path), reply_parameters=reply_params()
            )
        except TelegramRetryAfter as e:
            await asyncio.sleep(e.retry_after)
            await bot.send_document(
                chat_id,
                FSInputFile(audio_path),
                caption=caption,
                reply_parameters=reply_params(),
            )
            await bot.send_voice(
                chat_id, FSInputFile(audio_path), reply_parameters=reply_params()
            )

        if status_msg_id:
            try:
                await bot.delete_message(chat_id, status_msg_id)
            except TelegramAPIError:
                pass

        # The audio is delivered — nothing below may fail the job (it would
        # refund and show an error for a successful conversion).
        await increment_daily_count(user_id)
        try:
            async with get_db() as db:
                user_service = UserService(db)
                await check_and_notify_rewards(
                    bot, chat_id, user_id, user_service, lang
                )
                await post_conversion_upsell(
                    bot,
                    chat_id,
                    user_id,
                    lang,
                    user_service,
                    job.get("is_lifetime", False),
                )
        except Exception:
            logging.exception(f"Post-conversion steps failed for user {user_id}")

    finally:
        for path in (video_path, audio_path):
            if path and os.path.exists(path):
                os.remove(path)
