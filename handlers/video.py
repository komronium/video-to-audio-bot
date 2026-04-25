import asyncio
import logging
import os
import re
from datetime import datetime
from urllib.parse import quote_plus

import redis.asyncio as aioredis
from aiogram import F, Router
from aiogram.exceptions import TelegramAPIError, TelegramRetryAfter
from aiogram.types import Document, FSInputFile, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy.ext.asyncio import AsyncSession

from config import settings
from services.converter import VideoConverter, NoAudioError
from services.redis_queue import queue_manager
from services.user_service import UserService
from utils.i18n import i18n
from utils.rewards import check_and_notify_rewards

MAX_FILE_SIZE = 50 * 1024 * 1024
DAILY_LIMIT = 5
MAX_QUEUE_SIZE = 50
MAX_CONCURRENT = 5

conversion_semaphore = asyncio.Semaphore(MAX_CONCURRENT)

_redis = aioredis.Redis(host="localhost", port=6379, decode_responses=True)
_bot_username: str | None = None

router = Router()


async def _get_bot_username(bot) -> str:
    global _bot_username
    if _bot_username is None:
        me = await bot.get_me()
        _bot_username = me.username
    return _bot_username


async def get_buy_more_keyboard(lang: str, user_service: UserService, user_id: int, bot):
    builder = InlineKeyboardBuilder()
    builder.button(text=i18n.get_text("buy-extra", lang), callback_data="diamond:list")
    builder.button(text=i18n.get_text("get-lifetime", lang), callback_data="diamond:lifetime")
    code = await user_service.generate_referral_code(user_id)
    bot_username = await _get_bot_username(bot)
    referral_link = f"https://t.me/{bot_username}?start={code}"
    share_text = i18n.get_text("referral-share-text", lang)
    share_url = f"https://t.me/share/url?url={quote_plus(referral_link)}&text={quote_plus(share_text)}"
    builder.button(text=i18n.get_text("invite-friend", lang), url=share_url)
    builder.adjust(1)
    return builder.as_markup()


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


async def _get_daily_count(user_id: int) -> int:
    today = datetime.today().strftime("%Y-%m-%d")
    return int(await _redis.get(f"user:{user_id}:{today}") or 0)


async def _get_daily_ttl(user_id: int) -> int:
    today = datetime.today().strftime("%Y-%m-%d")
    return await _redis.ttl(f"user:{user_id}:{today}")


async def _increment_daily_count(user_id: int):
    today = datetime.today().strftime("%Y-%m-%d")
    key = f"user:{user_id}:{today}"
    if not await _redis.exists(key):
        await _redis.set(key, 1)
        await _redis.expire(key, 86400)
    else:
        await _redis.incr(key)


@router.message(F.video)
async def video_handler(message: Message, db: AsyncSession, document: Document = None):
    user_service = UserService(db)
    user = await user_service.get_user(message.from_user.id)
    if not user:
        tg = message.from_user
        user = await user_service.add_user(
            tg.id, tg.username, tg.full_name, tg.language_code or "en", message.bot
        )
    lang = user.lang or "en"
    is_lifetime = user.is_premium
    user_id = message.from_user.id

    video = message.video if document is None else document

    # Large file check
    if video.file_size > MAX_FILE_SIZE:
        if not is_lifetime:
            if user.diamonds > 0:
                if not await user_service.use_diamond(user.user_id):
                    await message.reply(
                        i18n.get_text("no-diamonds", lang),
                        reply_markup=await get_buy_more_keyboard(lang, user_service, user.user_id, message.bot),
                    )
                    return
                await message.answer(i18n.get_text("large-used", lang))
            else:
                size_mb = MAX_FILE_SIZE // (1024 * 1024)
                await message.reply(
                    i18n.get_text("too-large", lang).format(size_mb)
                    + "\n\n"
                    + i18n.get_text("limit-invite-tip", lang),
                    reply_markup=await get_buy_more_keyboard(lang, user_service, user.user_id, message.bot),
                )
                return

    # Daily limit check
    current = await _get_daily_count(user_id)
    if not is_lifetime and current + 1 > DAILY_LIMIT:
        if user.diamonds > 0:
            if not await user_service.use_diamond(user.user_id):
                await message.reply(
                    i18n.get_text("no-diamonds", lang),
                    reply_markup=await get_buy_more_keyboard(lang, user_service, user.user_id, message.bot),
                )
                return
            await message.answer(i18n.get_text("extra-used", lang))
        else:
            ttl = await _get_daily_ttl(user_id)
            if ttl > 0:
                hours, minutes = ttl // 3600, (ttl % 3600) // 60
                time_str = f"{hours}h {minutes}m" if hours else f"{minutes}m"
                limit_text = i18n.get_text("daily-limit", lang) + f"\n\n⏳ <b>{time_str}</b>"
            else:
                limit_text = i18n.get_text("daily-limit", lang)
            await message.answer(
                limit_text + "\n\n" + i18n.get_text("limit-invite-tip", lang),
                reply_markup=await get_buy_more_keyboard(lang, user_service, user.user_id, message.bot),
            )
            return

    timestamp = int(message.date.timestamp())

    if await queue_manager.queue_length() >= MAX_QUEUE_SIZE:
        await message.reply(i18n.get_text("server-busy", lang))
        return

    if await queue_manager.user_in_queue(user_id):
        await message.reply(i18n.get_text("queue-wait", lang))
        return

    queue_position = await queue_manager.add_to_queue(user_id, video.file_id, timestamp)
    queue_length = await queue_manager.queue_length()
    queue_message = None

    if queue_position > 1:
        try:
            queue_message = await message.reply(
                i18n.get_text("queue", lang).format(queue_position, queue_length)
            )
        except TelegramAPIError:
            pass

    try:
        async with conversion_semaphore:
            if queue_message:
                try:
                    await queue_message.delete()
                except TelegramAPIError:
                    pass
            await _process_video(message, db, video, lang, user_service)
    except TelegramRetryAfter as e:
        logging.warning(f"FloodControl for user {user_id}, retry after {e.retry_after}s")
    except Exception as e:
        logging.exception(f"Error processing video for user {user_id}")
        try:
            await message.reply(i18n.get_text("error-server", lang))
        except TelegramAPIError:
            pass
        try:
            await message.bot.send_message(
                settings.ADMIN_ID,
                f"<b>❌ Video processing error</b>\n"
                f"<b>User:</b> <code>{user_id}</code>\n"
                f"<b>Error:</b> <code>{e}</code>\n"
                f"<b>Queue size:</b> {await queue_manager.queue_length()}",
            )
        except TelegramAPIError:
            pass
    finally:
        await queue_manager.remove_from_queue(user_id, video.file_id, timestamp)


@router.message(F.document.mime_type.startswith("video"))
async def document_handler(message: Message, db: AsyncSession):
    await video_handler(message, db, message.document)


async def _process_video(
    message: Message,
    db: AsyncSession,
    video,
    lang: str,
    user_service: UserService,
):
    user_id = message.from_user.id
    processing_msg = None
    video_path = None
    audio_path = None

    try:
        processing_msg = await message.reply(i18n.get_text("downloading", lang))

        file = await message.bot.get_file(video.file_id)
        video_path = file.file_path

        file_name = _generate_name(message, video)
        await processing_msg.edit_text(i18n.get_text("converting", lang))

        try:
            audio_path = await VideoConverter().convert_video_to_audio(
                video_path, f"audios/{file_name}"
            )
        except NoAudioError:
            await processing_msg.edit_text(i18n.get_text("no-audio", lang))
            return

        if isinstance(audio_path, dict):
            await processing_msg.edit_text(i18n.get_text("error-server", lang))
            await message.bot.send_message(
                settings.ADMIN_ID,
                f"<b>❌ Video converting ERROR</b>\n"
                f"<blockquote>{audio_path['message']}</blockquote>",
            )
            return

        bot_username = await _get_bot_username(message.bot)
        caption = i18n.get_text("converted-by", lang).format(bot_username)

        await user_service.add_conversation(user_id=user_id)
        await processing_msg.delete()
        processing_msg = None

        try:
            await message.reply_document(FSInputFile(path=audio_path), caption=caption)
            await message.reply_voice(FSInputFile(path=audio_path))
        except TelegramRetryAfter as e:
            await asyncio.sleep(e.retry_after)
            await message.reply_document(FSInputFile(path=audio_path), caption=caption)
            await message.reply_voice(FSInputFile(path=audio_path))

        await _increment_daily_count(user_id)
        await check_and_notify_rewards(message, user_id, user_service, lang)

    except Exception:
        if processing_msg:
            try:
                await processing_msg.edit_text(i18n.get_text("error-server", lang))
            except TelegramAPIError:
                pass
        raise
    finally:
        if video_path and os.path.exists(video_path):
            os.remove(video_path)
        if audio_path and os.path.exists(audio_path):
            os.remove(audio_path)
