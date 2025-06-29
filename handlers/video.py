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

from config import settings

MAX_FILE_SIZE = 150 * 1024 * 1024
DAILY_LIMIT = 5

r = redis.Redis(host='localhost', port=6379, decode_responses=True)

router = Router()


def get_buy_more_keyboard():
    builder = InlineKeyboardBuilder()
    builder.button(text="Buy Extra Diamonds 💎", callback_data="buy_diamonds")
    builder.button(text="💎 Get Lifetime Premium", callback_data="lifetime")
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
    is_lifetime = await user_service.is_lifetime(user.id)

    video = message.video if not document else document
    if video.file_size > MAX_FILE_SIZE:
        if not is_lifetime and user.diamonds <= 0:
            await message.bot.send_chat_action(message.chat.id, 'typing')
            await message.reply(
                "💎 <b>File too large!</b>\n"
                "Your video exceeds the 150 MB limit for free users.\n\n"
                "You can use a diamond to unlock this feature, buy diamonds below.",
                reply_markup=get_buy_more_keyboard()
            )
            return
        elif not is_lifetime:
            used = await user_service.use_diamond(user.user_id)
            if used:
                await message.answer("<b>💎 1 diamond used for large file upload.</b>")
            else:
                await message.reply(
                    "💎 <b>No diamonds left!</b> Please buy more diamonds to continue.",
                    reply_markup=get_buy_more_keyboard()
                )
                return

    user_id = message.from_user.id
    today = datetime.today().strftime('%Y-%m-%d')
    key = f'user:{user_id}:{today}'

    count = r.get(key)

    if count and int(count) >= DAILY_LIMIT:
        if not is_lifetime and user.diamonds <= 0:
            await message.answer(
                "💎 <b>Daily limit reached!</b>\n"
                "You have used your daily free conversations.\n\n"
                "You can use a diamond to unlock extra conversations, buy below.",
                reply_markup=get_buy_more_keyboard()
            )
            return
        elif not is_lifetime:
            used = await user_service.use_diamond(user.user_id)
            if used:
                await message.answer("<b>💎 1 diamond used for extra conversation.</b>")
            else:
                await message.reply(
                    "💎 <b>No diamonds left!</b> Please buy more diamonds to continue.",
                    reply_markup=get_buy_more_keyboard()
                )
                return
    
    timestamp = int(message.date.timestamp())
    queue_position = queue_manager.add_to_queue(user_id, video.file_id, timestamp)
    query_length = queue_manager.queue_length()
    queue_message = None

    if queue_position > 1:
        queue_message = await message.reply(
            "⏳ Your request is in queue. Please wait ...\n"
            f"Position: <b>{queue_position} / {query_length}</b>"
        )
        queue_position = queue_manager.get_queue_position(user_id, video.file_id, timestamp)
        query_length = queue_manager.queue_length()
        await asyncio.sleep(2)

    while queue_position > 1:
        try:
            await queue_message.edit_text(
                "⏳ Your request is in queue. Please wait ...\n"
                f"Position: <b>{queue_position} / {query_length}</b>"
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

    await process_video(message, db, video)


@router.message(F.document.mime_type.startswith('video'))
async def document_handler(message: Message, db: AsyncSession):
    await video_handler(message, db, message.document)


async def process_video(message: Message, db: AsyncSession, video):
    user_id = message.from_user.id
    processing_msg = await message.reply("Downloading ...")

    file = await message.bot.get_file(video.file_id)
    video_path = file.file_path
    audio_path = None

    try:
        file_name = generate_name(message, video)

        await processing_msg.edit_text("Converting ...")

        audio_path = await VideoConverter().convert_video_to_audio(video_path, f'audios/{file_name}')

        if type(audio_path) is dict:
            await processing_msg.edit_text("❌ Error. Please try again later!")
            await message.bot.send_message(settings.ADMIN_ID, f"<b>❌ Video converting ERROR</b>\n"
                                                              f"<blockquote>{audio_path['message']}</blockquote>\n")
            return

        audio_file = FSInputFile(path=audio_path)

        bot = await message.bot.get_me()
        await UserService(db).add_conversation(message.from_user.id)
        await processing_msg.delete()
        await message.reply_document(audio_file, caption=f'Converted by @{bot.username}')

        await message.answer('<b>⭐️ Exchange Telegram Stars to TON / USDT</b>\n'
                             '⭐️ <a href="https://t.me/TelegStarsWalletBot?start=_tgr_eaqwdbsxZTU6"><b>Click here</b></a>')

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
