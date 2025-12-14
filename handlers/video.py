import os
import asyncio
import redis
import re
from datetime import datetime
from aiogram import Router, F
from aiogram.types import Message, FSInputFile, Document
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.exceptions import TelegramAPIError
from sqlalchemy.ext.asyncio import AsyncSession

from services.converter import VideoConverter
from services.user_service import UserService
from services.redis_queue import queue_manager
from utils.i18n import i18n

from config import settings

MAX_FILE_SIZE = 25 * 1024 * 1024
DAILY_LIMIT = 5

r = redis.Redis(host='localhost', port=6379, decode_responses=True)

router = Router()


def get_buy_more_keyboard(lang: str):
    builder = InlineKeyboardBuilder()
    builder.button(text=i18n.get_text('buy-extra', lang), callback_data="buy_diamonds")
    builder.button(text=i18n.get_text('get-lifetime', lang), callback_data="lifetime")
    builder.adjust(1)
    return builder.as_markup()


def generate_name(message: Message, video) -> str:
    def sanitize_filename(name: str) -> str:
        return re.sub(r'[^a-zA-Z0-9_-]', '', name)

    if message.caption:
        caption = message.caption[:25] if len(message.caption) > 25 else message.caption
        return sanitize_filename(caption.lower().replace(' ', '_'))
    
    if video.file_name:
        file_name = video.file_name.rsplit('.', 1)[0]
        return sanitize_filename(file_name.lower().replace(' ', '_'))
    
    user_id = message.from_user.id
    timestamp = datetime.now().timestamp()
    return f"audio_{user_id}_{timestamp}.mp3"


@router.message(F.video)
async def video_handler(message: Message, db: AsyncSession, document: Document = None):
    user_service = UserService(db)
    user = await user_service.get_user(message.from_user.id)
    lang = await user_service.get_lang(message.from_user.id)
    is_lifetime = await user_service.is_lifetime(user.user_id) if user else False

    video = message.video if not document else document
    if video.file_size > MAX_FILE_SIZE:
        if not is_lifetime and user.diamonds <= 0:
            await message.bot.send_chat_action(message.chat.id, 'typing')
            size_mb = int(MAX_FILE_SIZE / (1024 * 1024))
            await message.reply(i18n.get_text('too-large', lang).format(size_mb), reply_markup=get_buy_more_keyboard(lang))
            return
        elif not is_lifetime:
            used = await user_service.use_diamond(user.user_id)
            if used:
                await message.answer(i18n.get_text('large-used', lang))
            else:
                await message.reply(
                    "💎 <b>No diamonds left!</b> Please buy more diamonds to continue.",
                    reply_markup=get_buy_more_keyboard(lang)
                )
                return

    user_id = message.from_user.id

    
    today = datetime.today().strftime('%Y-%m-%d')
    key = f'user:{user_id}:{today}'

    count = r.get(key)

    if count and int(count) >= DAILY_LIMIT:
        if not is_lifetime and user.diamonds <= 0:
            await message.answer(
                i18n.get_text('daily-limit', lang),
                reply_markup=get_buy_more_keyboard(lang)
            )
            return
        elif not is_lifetime:
            used = await user_service.use_diamond(user.user_id)
            if used:
                await message.answer(i18n.get_text('extra-used', lang))
            else:
                await message.reply(
                    "💎 <b>No diamonds left!</b> Please buy more diamonds to continue.",
                    reply_markup=get_buy_more_keyboard(lang)
                )
                return
    
    timestamp = int(message.date.timestamp())
    queue_position = queue_manager.add_to_queue(user_id, video.file_id, timestamp)
    query_length = queue_manager.queue_length()
    queue_message = None

    def format_queue_message(pos: int, total: int, anim: str = "⏳") -> str:
        """Format queue message with progress bar and animation"""
        if total == 0:
            total = 1
        progress = max(0, min(100, int((total - pos + 1) / total * 100)))
        filled = int(progress / 10)
        bar = "█" * filled + "░" * (10 - filled)
        return i18n.get_text('queue', lang).format(anim, pos, total, progress, bar)

    animations = ["⏳", "🔄"]
    anim_index = 0
    
    if queue_position > 1:
        queue_message = await message.reply(
            format_queue_message(queue_position, query_length, animations[anim_index])
        )
        queue_position = queue_manager.get_queue_position(user_id, video.file_id, timestamp)
        query_length = queue_manager.queue_length()
        await asyncio.sleep(2)

    while queue_position > 1:
        try:
            anim_index = (anim_index + 1) % len(animations)
            await queue_message.edit_text(
                format_queue_message(queue_position, query_length, animations[anim_index])
            )
            await asyncio.sleep(1)
            queue_position = queue_manager.get_queue_position(user_id, video.file_id, timestamp)
            query_length = queue_manager.queue_length()
        except TelegramAPIError:
            await asyncio.sleep(1)
            queue_position = queue_manager.get_queue_position(user_id, video.file_id, timestamp)
            query_length = queue_manager.queue_length()
    
    if queue_message:
        await queue_message.delete()

    # If overall queue is too long, cancel the FIRST queued user's task (position 1)
    try:
        if queue_manager.queue_length() > 10:
            # Peek first item in redis queue (format: user_id:file_id:timestamp)
            first_item = r.lindex(queue_manager.queue_key, 0)
            if first_item:
                parts = first_item.split(":")
                if len(parts) >= 3:
                    target_user_id = int(parts[0])
                    target_file_id = parts[1]
                    target_ts = int(parts[2])

                    # get target user's language if possible
                    target_user = await user_service.get_user(target_user_id)
                    target_lang = await user_service.get_lang(target_user_id)

                    # notify the target user to try again later
                    try:
                        text = i18n.get_text('try-again', target_lang) or "Please try again later."
                        await message.bot.send_message(target_user_id, text)
                    except Exception:
                        pass

                    # notify group which user was canceled
                    display_name = (target_user.name if target_user and target_user.name else message.from_user.full_name) or "User"
                    mention = f'<a href="tg://user?id={target_user_id}">{display_name}</a>'
                    try:
                        await message.bot.send_message(
                            settings.GROUP_ID,
                            f"⚠️ <b>Queue limit exceeded</b>\n{mention} — task canceled because queue length > 10.",
                            parse_mode='HTML'
                        )
                    except Exception:
                        pass

                    # remove that first queued task
                    queue_manager.remove_from_queue(target_user_id, target_file_id, target_ts)
                    return
    except Exception:
        # If anything goes wrong with notifying/removing, safely continue to processing
        pass

    await process_video(message, db, video, lang)


@router.message(F.document.mime_type.startswith('video'))
async def document_handler(message: Message, db: AsyncSession):
    await video_handler(message, db, message.document)


async def process_video(message: Message, db: AsyncSession, video, lang: str):
    user_id = message.from_user.id
    processing_msg = await message.reply(i18n.get_text('downloading', lang))

    file = await message.bot.get_file(video.file_id)
    video_path = file.file_path
    audio_path = None

    try:
        file_name = generate_name(message, video)

        await processing_msg.edit_text(i18n.get_text('converting', lang))

        audio_path = await VideoConverter().convert_video_to_audio(video_path, f'audios/{file_name}')

        if isinstance(audio_path, dict):
            # Specific case: video has no audio track
            if audio_path.get('code') == 'NO_AUDIO':
                await processing_msg.edit_text(i18n.get_text('no-audio', lang))
                return

            # Generic error – notify user and admin
            await processing_msg.edit_text("❌ Error. Please try again later!")
            await message.bot.send_message(
                settings.ADMIN_ID,
                f"<b>❌ Video converting ERROR</b>\n"
                f"<blockquote>{audio_path.get('message', 'Unknown error')}</blockquote>\n"
            )
            return

        audio_file = FSInputFile(path=audio_path)

        bot = await message.bot.get_me()
        await UserService(db).add_conversation(message.from_user.id)
        await processing_msg.delete()
        await message.reply_document(audio_file, caption=i18n.get_text('converted-by', lang).format(bot.username))
        

        today = datetime.today().strftime('%Y-%m-%d')
        key = f'user:{user_id}:{today}'
        if not r.exists(key):
            r.set(key, 1)
            r.expire(key, 86400)
        else:
            r.incr(key)
    finally:
        timestamp = int(message.date.timestamp())
        queue_manager.remove_from_queue(user_id, video.file_id, timestamp)

        os.remove(video_path)
        if audio_path and os.path.exists(audio_path):
            os.remove(audio_path)
