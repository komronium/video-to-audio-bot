from aiogram import types, Router, F, Bot
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession
import asyncio

from config import settings
from services.user_service import UserService
from utils.i18n import i18n


router = Router()


BTN_STATS_EXTENDED = "📊 Stats+"
BTN_RESTART = "🔁 Restart"
BTN_UPDATE = "⬇️ Update"
BTN_LANGS = "🌍 Langs"
BTN_DEF_LANGS = "📈 DefLangs"
BTN_BACK = "⬅️ Back"
BTN_ADMIN = "Admin"


def is_admin(user_id: int) -> bool:
    return user_id == settings.ADMIN_ID


async def run_shell_commands(commands: list[str]) -> tuple[int, str, str]:
    proc = await asyncio.create_subprocess_shell(
        " && ".join(commands),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await proc.communicate()
    return proc.returncode, stdout.decode().strip(), stderr.decode().strip()

def get_admin_keyboard(lang: str) -> ReplyKeyboardMarkup:
    keyboard = [
        [
            KeyboardButton(text=BTN_STATS_EXTENDED),
            KeyboardButton(text=BTN_RESTART),
        ],
        [
            KeyboardButton(text=BTN_UPDATE),
            KeyboardButton(text=BTN_LANGS),
            KeyboardButton(text=BTN_DEF_LANGS),
        ],
        [
            KeyboardButton(text=BTN_BACK),
        ],
    ]
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)


def get_confirm_keyboard(action: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Yes", callback_data=f"admin:{action}:yes"),
            InlineKeyboardButton(text="❌ No", callback_data=f"admin:{action}:no"),
        ]
    ])


@router.message(F.text == BTN_ADMIN)
async def admin_menu_btn(message: types.Message, db: AsyncSession):
    if not is_admin(message.from_user.id):
        return
    lang = await UserService(db).get_lang(message.from_user.id)
    await message.answer("Admin menu:", reply_markup=get_admin_keyboard(lang))


@router.message(F.text == BTN_STATS_EXTENDED)
async def admin_extended_stats(message: types.Message, db: AsyncSession):
    if not is_admin(message.from_user.id):
        return
    # Call internal admin stats logic directly
    from .stats import adminstats_internal
    await adminstats_internal(message, db)


@router.message(F.text == BTN_RESTART)
async def admin_restart_bot(message: types.Message):
    if not is_admin(message.from_user.id):
        return
    await message.answer("Confirm restart?", reply_markup=get_confirm_keyboard("restart"))


@router.message(F.text == BTN_UPDATE)
async def admin_update_bot(message: types.Message):
    if not is_admin(message.from_user.id):
        return
    await message.answer("Confirm update?", reply_markup=get_confirm_keyboard("update"))


@router.callback_query(F.data == "admin:restart:yes")
async def confirm_restart_yes(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        await call.answer()
        return
    await call.message.edit_text("Restarting…")
    try:
        code, out, err = await run_shell_commands([
            "sudo systemctl restart video-to-audio-bot",
        ])
        if code in [0, -15]:
            await call.message.edit_text("✅ Restarted")
        else:
            await call.message.edit_text(f"❌ Restart failed: <code>{err or out or 'Unknown error'}</code>")
    except Exception as e:
        await call.message.edit_text(f"❌ Exception: <code>{e}</code>")
    await call.answer()


@router.callback_query(F.data == "admin:restart:no")
async def confirm_restart_no(call: CallbackQuery):
    if is_admin(call.from_user.id):
        await call.message.edit_text("Cancelled")
    await call.answer()


@router.callback_query(F.data == "admin:update:yes")
async def confirm_update_yes(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        await call.answer()
        return
    await call.message.edit_text("Updating…")
    try:
        code, out, err = await run_shell_commands([
            "git pull --rebase --autostash",
            "sudo systemctl daemon-reload",
            "sudo systemctl restart video-to-audio-bot",
        ])
        if code in [0, -15]:
            last_lines = out.splitlines()[-10:] if out else []
            snippet = "\n".join(last_lines)
            msg = "✅ Updated and restarted." + (f"\n<code>{snippet}</code>" if snippet else "")
            await call.message.edit_text(msg)
        else:
            await call.message.edit_text(f"❌ Update failed: <code>{err or out or 'Unknown error'}</code>")
    except Exception as e:
        await call.message.edit_text(f"❌ Exception: <code>{e}</code>")
    await call.answer()


@router.callback_query(F.data == "admin:update:no")
async def confirm_update_no(call: CallbackQuery):
    if is_admin(call.from_user.id):
        await call.message.edit_text("Cancelled")
    await call.answer()


@router.message(F.text == BTN_LANGS)
async def admin_languages(message: types.Message, db: AsyncSession):
    if not is_admin(message.from_user.id):
        return
    from .stats import langs_internal
    await langs_internal(message, db)


@router.message(F.text == BTN_DEF_LANGS)
async def admin_default_langs(message: types.Message, db: AsyncSession, bot: Bot):
    if not is_admin(message.from_user.id):
        return
    from .stats import deflangs_internal
    await deflangs_internal(message, db, bot)


@router.message(F.text.in_([BTN_BACK]))
async def admin_back(message: types.Message, db: AsyncSession):
    # Return to common menu
    from .start import get_menu_keyboard
    service = UserService(db)
    lang = await service.get_lang(message.from_user.id)
    await message.answer(i18n.get_text('start', lang), reply_markup=get_menu_keyboard(lang, True))


