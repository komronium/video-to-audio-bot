from aiogram import types, Router, F
from aiogram.filters import Command
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from sqlalchemy.ext.asyncio import AsyncSession
import asyncio

from config import settings
from services.user_service import UserService
from utils.i18n import i18n


router = Router()


def get_admin_keyboard(lang: str) -> ReplyKeyboardMarkup:
    keyboard = [
        [
            KeyboardButton(text="📊 Extended stats"),
            KeyboardButton(text="🔁 Restart bot"),
        ],
        [
            KeyboardButton(text="⬅️ Back"),
        ],
    ]
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)


@router.message(Command('admin'))
async def admin_menu_cmd(message: types.Message, db: AsyncSession):
    if message.from_user.id != settings.ADMIN_ID:
        return
    lang = await UserService(db).get_lang(message.from_user.id)
    await message.answer("Admin menu:", reply_markup=get_admin_keyboard(lang))


@router.message(F.text == "Admin")
async def admin_menu_btn(message: types.Message, db: AsyncSession):
    if message.from_user.id != settings.ADMIN_ID:
        return
    lang = await UserService(db).get_lang(message.from_user.id)
    await message.answer("Admin menu:", reply_markup=get_admin_keyboard(lang))


@router.message(F.text == "📊 Extended stats")
async def admin_extended_stats(message: types.Message, db: AsyncSession):
    if message.from_user.id != settings.ADMIN_ID:
        return
    # Reuse existing /adminstats logic by invoking the command handler via message bot API
    # Alternatively, import and call the function. We'll send the command text to keep it simple.
    await message.bot.delete_message(message.chat.id, message.message_id) if message.chat.type in ("private", "group", "supergroup") else None
    await message.answer("/adminstats")


@router.message(F.text == "🔁 Restart bot")
async def admin_restart_bot(message: types.Message):
    if message.from_user.id != settings.ADMIN_ID:
        return
    await message.answer("Restarting service…")
    try:
        proc = await asyncio.create_subprocess_shell(
            "sudo systemctl restart video-to-aduio-bot",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()
        if proc.returncode == 0:
            await message.answer("✅ Bot restart command sent.")
        else:
            err = stderr.decode().strip() or stdout.decode().strip() or "Unknown error"
            await message.answer(f"❌ Failed to restart: <code>{err}</code>")
    except Exception as e:
        await message.answer(f"❌ Exception: <code>{e}</code>")


@router.message(F.text.in_(["⬅️ Back"]))
async def admin_back(message: types.Message, db: AsyncSession):
    # Return to common menu
    from .start import get_menu_keyboard
    service = UserService(db)
    lang = await service.get_lang(message.from_user.id)
    is_admin = message.from_user.id == settings.ADMIN_ID
    await message.answer(i18n.get_text('start', lang), reply_markup=get_menu_keyboard(lang, is_admin))


