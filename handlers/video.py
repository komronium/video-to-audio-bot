import asyncio
import logging
import os
import re
from datetime import datetime
from urllib.parse import quote_plus

import redis
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

MAX_FILE_SIZE = 50 * 1024 * 1024
DAILY_LIMIT = 5
MAX_QUEUE_SIZE = 50
MAX_CONCURRENT = 5

conversion_semaphore = asyncio.Semaphore(MAX_CONCURRENT)

r = redis.Redis(host="localhost", port=6379, decode_responses=True)

router = Router()


async def get_buy_more_keyboard(lang: str, user_service: UserService, user_id: int, bot):
    builder = InlineKeyboardBuilder()
    builder.button(text=i18n.get_text("buy-extra", lang), callback_data="diamond:list")
    builder.button(
        text=i18n.get_text("get-lifetime", lang), callback_data="diamond:lifetime"
    )
    code = await user_service.generate_referral_code(user_id)
    bot_username = (await bot.get_me()).username
    referral_link = f"https://t.me/{bot_username}?start={code}"
    share_text = i18n.get_text("referral-share-text", lang)
    share_url = f"https://t.me/share/url?url={quote_plus(referral_link)}&text={quote_plus(share_text)}"
    builder.button(text=i18n.get_text("invite-friend", lang), url=share_url)
    builder.adjust(1)
    return builder.as_markup()


def generate_name(message: Message, video) -> str:
    def sanitize_filename(name: str) -> str:
        return re.sub(r"[^a-zA-Z0-9_-]", "", name)

    if message.caption:
        caption = message.caption[:25] if len(message.caption) > 25 else message.caption
        return sanitize_filename(caption.lower().replace(" ", "_"))

    if video.file_name:
        file_name = video.file_name.rsplit(".", 1)[0]
        return sanitize_filename(file_name.lower().replace(" ", "_"))

    user_id = message.from_user.id
    timestamp = datetime.now().timestamp()
    return f"audio_{user_id}_{timestamp}.mp3"


@router.message(F.video)
async def video_handler(message: Message, db: AsyncSession, document: Document = None):
    user_service = UserService(db)
    user = await user_service.get_user(message.from_user.id)
    if not user:
        tg_user = message.from_user
        user = await user_service.add_user(
            tg_user.id, tg_user.username, tg_user.full_name,
            tg_user.language_code or "en", message.bot
        )
    lang = user.lang or "en"
    is_lifetime = user.is_premium

    video = message.video if not document else document
    if video.file_size > MAX_FILE_SIZE:
        if not is_lifetime and user.diamonds <= 0:
            await message.bot.send_chat_action(message.chat.id, "typing")
            size_mb = int(MAX_FILE_SIZE / (1024 * 1024))
            await message.reply(
                i18n.get_text("too-large", lang).format(size_mb)
                + "\n\n"
                + i18n.get_text("limit-invite-tip", lang),
                reply_markup=await get_buy_more_keyboard(
                    lang, user_service, user.user_id, message.bot
                ),
            )
            return
        elif not is_lifetime:
            used = await user_service.use_diamond(user.user_id)
            if used:
                await message.answer(i18n.get_text("large-used", lang))
            else:
                await message.reply(
                    i18n.get_text("no-diamonds", lang),
                    reply_markup=await get_buy_more_keyboard(
                        lang, user_service, user.user_id, message.bot
                    ),
                )
                return

    user_id = message.from_user.id

    today = datetime.today().strftime("%Y-%m-%d")
    key = f"user:{user_id}:{today}"

    count = r.get(key)
    current = int(count or 0)

    if not is_lifetime and current + 1 > DAILY_LIMIT:
        if user.diamonds <= 0:
            ttl = r.ttl(key)
            if ttl and ttl > 0:
                hours = ttl // 3600
                minutes = (ttl % 3600) // 60
                time_str = f"{hours}h {minutes}m" if hours else f"{minutes}m"
                limit_text = i18n.get_text("daily-limit", lang) + f"\n\n⏳ <b>{time_str}</b>"
            else:
                limit_text = i18n.get_text("daily-limit", lang)
            await message.answer(
                limit_text + "\n\n" + i18n.get_text("limit-invite-tip", lang),
                reply_markup=await get_buy_more_keyboard(
                    lang, user_service, user.user_id, message.bot
                ),
            )
            return
        elif not is_lifetime:
            used = await user_service.use_diamond(user.user_id)
            if used:
                await message.answer(i18n.get_text("extra-used", lang))
            else:
                await message.reply(
                    i18n.get_text("no-diamonds", lang),
                    reply_markup=await get_buy_more_keyboard(
                        lang, user_service, user.user_id, message.bot
                    ),
                )
                return

    timestamp = int(message.date.timestamp())

    current_queue_size = queue_manager.queue_length()
    if current_queue_size >= MAX_QUEUE_SIZE:
        await message.reply(
            i18n.get_text("server-busy", lang)
            if i18n.get_text("server-busy", lang) != "server-busy"
            else i18n.get_text("error-server", lang)
        )
        return

    if queue_manager.user_in_queue(user_id):
        await message.reply(i18n.get_text("queue-wait", lang))
        return

    queue_position = queue_manager.add_to_queue(user_id, video.file_id, timestamp)
    queue_length = queue_manager.queue_length()
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
            await process_video(message, db, video, lang)
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
                f"<b>Queue size:</b> {queue_manager.queue_length()}",
            )
        except TelegramAPIError:
            pass
    finally:
        queue_manager.remove_from_queue(user_id, video.file_id, timestamp)


@router.message(F.document.mime_type.startswith("video"))
async def document_handler(message: Message, db: AsyncSession):
    await video_handler(message, db, message.document)


async def process_video(message: Message, db: AsyncSession, video, lang: str):
    user_id = message.from_user.id
    user_service = UserService(db)
    processing_msg = None
    video_path = None
    audio_path = None

    try:
        processing_msg = await message.reply(i18n.get_text("downloading", lang))

        file = await message.bot.get_file(video.file_id)
        video_path = file.file_path

        file_name = generate_name(message, video)
        await processing_msg.edit_text(i18n.get_text("converting", lang))

        try:
            audio_path = await VideoConverter().convert_video_to_audio(
                video_path, f"audios/{file_name}"
            )
        except NoAudioError:
            await processing_msg.edit_text(i18n.get_text("no-audio", lang))
            return

        if type(audio_path) is dict:
            await processing_msg.edit_text(i18n.get_text("error-server", lang))
            await message.bot.send_message(
                settings.ADMIN_ID,
                f"<b>❌ Video converting ERROR</b>\n"
                f"<blockquote>{audio_path['message']}</blockquote>\n",
            )
            return

        audio_file = FSInputFile(path=audio_path)
        bot = await message.bot.get_me()
        await UserService(db).add_conversation(user_id=message.from_user.id)
        await processing_msg.delete()
        processing_msg = None

        try:
            await message.reply_document(
                audio_file, caption=i18n.get_text("converted-by", lang).format(bot.username)
            )
        except TelegramRetryAfter as e:
            await asyncio.sleep(e.retry_after)
            await message.reply_document(
                audio_file, caption=i18n.get_text("converted-by", lang).format(bot.username)
            )

        today = datetime.today().strftime("%Y-%m-%d")
        key = f"user:{user_id}:{today}"
        if not r.exists(key):
            r.set(key, 1)
            r.expire(key, 86400)
        else:
            r.incr(key)

        # Referral reward check
        should_reward, inviter_id = await user_service.check_referral_reward(user_id)
        if should_reward:
            await user_service.grant_referral_reward(user_id)
            await message.answer(i18n.get_text("referral-bonus", lang))

        # Milestone reward check
        milestone_diamonds = await user_service.check_milestone_rewards(user_id)
        if milestone_diamonds > 0:
            await user_service.grant_milestone_reward(user_id, milestone_diamonds)
            await message.answer(i18n.get_text("milestone-bonus", lang).format(milestone_diamonds))

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
