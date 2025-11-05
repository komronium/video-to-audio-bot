from aiogram import types, Router, F, Bot
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
            KeyboardButton(text="⬇️ Update bot"),
            KeyboardButton(text="🌍 Languages"),
            KeyboardButton(text="📈 Default langs"),
        ],
        [
            KeyboardButton(text="⬅️ Back"),
        ],
    ]
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)


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
    # Call internal admin stats logic directly
    from .stats import adminstats_internal
    await adminstats_internal(message, db)


@router.message(F.text == "🔁 Restart bot")
async def admin_restart_bot(message: types.Message):
    if message.from_user.id != settings.ADMIN_ID:
        return
    await message.answer("Restarting service…")
    try:
        proc = await asyncio.create_subprocess_shell(
            "sudo systemctl restart video-to-audio-bot",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()
        if proc.returncode in [0, -15]:
            await message.answer("✅ Bot restart command sent.")
        else:
            err = stderr.decode().strip() or stdout.decode().strip() or "Unknown error"
            await message.answer(f"❌ Failed to restart: <code>{err}</code>")
    except Exception as e:
        await message.answer(f"❌ Exception: <code>{e}</code>")


@router.message(F.text == "⬇️ Update bot")
async def admin_update_bot(message: types.Message):
    if message.from_user.id != settings.ADMIN_ID:
        return
    await message.answer("Updating bot…")
    try:
        # Pull latest code, reload systemd units, and restart the service
        cmd = (
            "git pull --rebase --autostash && "
            "sudo systemctl daemon-reload && "
            "sudo systemctl restart video-to-audio-bot"
        )
        proc = await asyncio.create_subprocess_shell(
            cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()
        if proc.returncode in [0, -15]:
            out = stdout.decode().strip()
            msg = "✅ Updated and restarted.\n" + (f"<code>{out}</code>" if out else "")
            await message.answer(msg)
        else:
            err = stderr.decode().strip() or stdout.decode().strip() or "Unknown error"
            await message.answer(f"❌ Update failed: <code>{err}</code>")
    except Exception as e:
        await message.answer(f"❌ Exception: <code>{e}</code>")


@router.message(F.text == "🌍 Languages")
async def admin_languages(message: types.Message, db: AsyncSession):
    if message.from_user.id != settings.ADMIN_ID:
        return
    from .stats import langs_internal
    await langs_internal(message, db)


@router.message(F.text == "📈 Default langs")
async def admin_default_langs(message: types.Message, db: AsyncSession, bot: Bot):
    if message.from_user.id != settings.ADMIN_ID:
        return
    from .stats import deflangs_internal
    await deflangs_internal(message, db, bot)


@router.message(F.text.in_(["⬅️ Back"]))
async def admin_back(message: types.Message, db: AsyncSession):
    # Return to common menu
    from .start import get_menu_keyboard
    service = UserService(db)
    lang = await service.get_lang(message.from_user.id)
    is_admin = message.from_user.id == settings.ADMIN_ID
    await message.answer(i18n.get_text('start', lang), reply_markup=get_menu_keyboard(lang, is_admin))


