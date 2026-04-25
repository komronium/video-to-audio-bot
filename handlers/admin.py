import asyncio

from aiogram import types, Router, F, Bot
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import (
    ReplyKeyboardMarkup, KeyboardButton,
    InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery,
)
from sqlalchemy.ext.asyncio import AsyncSession

from config import settings
from database.session import get_db
from services.user_service import UserService
from states.admin import GiveDiamondsStates
from utils.i18n import i18n

router = Router()

BTN_STATS_EXTENDED = "📊 Stats+"
BTN_GIVE_DIAMONDS = "💎 Give"
BTN_DASHBOARD = "🖥 Dashboard"
BTN_RESTART = "🔁 Restart"
BTN_UPDATE = "⬇️ Update"
BTN_LANGS = "🌍 Langs"
BTN_DEF_LANGS = "📈 DefLangs"
BTN_BACK = "⬅️ Back"
BTN_ADMIN = "Admin"

WEBAPP_URL = f"http://{settings.SERVER_IP}:8001"


def is_admin(user_id: int) -> bool:
    return user_id == settings.ADMIN_ID


async def _run_commands(commands: list[str]) -> tuple[int, str, str]:
    proc = await asyncio.create_subprocess_shell(
        " && ".join(commands),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await proc.communicate()
    return proc.returncode, stdout.decode().strip(), stderr.decode().strip()


def get_admin_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=BTN_STATS_EXTENDED), KeyboardButton(text=BTN_GIVE_DIAMONDS)],
            [KeyboardButton(text=BTN_DASHBOARD)],
            [KeyboardButton(text=BTN_RESTART), KeyboardButton(text=BTN_UPDATE)],
            [KeyboardButton(text=BTN_LANGS), KeyboardButton(text=BTN_DEF_LANGS)],
            [KeyboardButton(text=BTN_BACK)],
        ],
        resize_keyboard=True,
    )


def _confirm_keyboard(action: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="✅ Yes", callback_data=f"admin:{action}:yes"),
        InlineKeyboardButton(text="❌ No", callback_data=f"admin:{action}:no"),
    ]])


@router.message(F.text == BTN_ADMIN)
async def admin_menu_btn(message: types.Message):
    if not is_admin(message.from_user.id):
        return
    await message.answer("Admin menu:", reply_markup=get_admin_keyboard())


@router.message(F.text == BTN_STATS_EXTENDED)
async def admin_extended_stats(message: types.Message, db: AsyncSession):
    if not is_admin(message.from_user.id):
        return
    from .stats import adminstats_internal
    await adminstats_internal(message, db)


@router.message(F.text == BTN_DASHBOARD)
async def admin_dashboard(message: types.Message):
    if not is_admin(message.from_user.id):
        return
    await message.answer(
        "🖥 <b>Admin Dashboard</b>",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="🌐 Open Dashboard", url=WEBAPP_URL)
        ]]),
    )


@router.message(F.text == BTN_RESTART)
async def admin_restart_bot(message: types.Message):
    if not is_admin(message.from_user.id):
        return
    await message.answer("Confirm restart?", reply_markup=_confirm_keyboard("restart"))


@router.message(F.text == BTN_UPDATE)
async def admin_update_bot(message: types.Message):
    if not is_admin(message.from_user.id):
        return
    await message.answer("Confirm update?", reply_markup=_confirm_keyboard("update"))


@router.callback_query(F.data == "admin:restart:yes")
async def confirm_restart(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        await call.answer()
        return
    await call.message.edit_text("Restarting…")
    try:
        code, out, err = await _run_commands(["sudo systemctl restart video-to-audio-bot"])
        if code in (0, -15):
            await call.message.edit_text("✅ Restarted")
        else:
            await call.message.edit_text(f"❌ Failed: <code>{err or out or 'Unknown error'}</code>")
    except Exception as e:
        await call.message.edit_text(f"❌ Exception: <code>{e}</code>")
    await call.answer()


@router.callback_query(F.data == "admin:restart:no")
async def cancel_restart(call: CallbackQuery):
    if is_admin(call.from_user.id):
        await call.message.edit_text("Cancelled")
    await call.answer()


@router.callback_query(F.data == "admin:update:yes")
async def confirm_update(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        await call.answer()
        return
    await call.message.edit_text("Updating…")
    try:
        code, out, err = await _run_commands([
            "git pull --rebase --autostash",
            "sudo systemctl daemon-reload",
            "sudo systemctl restart video-to-audio-bot",
        ])
        if code in (0, -15):
            snippet = "\n".join((out.splitlines() or [])[-10:])
            msg = "✅ Updated and restarted." + (f"\n<code>{snippet}</code>" if snippet else "")
            await call.message.edit_text(msg)
        else:
            await call.message.edit_text(f"❌ Failed: <code>{err or out or 'Unknown error'}</code>")
    except Exception as e:
        await call.message.edit_text(f"❌ Exception: <code>{e}</code>")
    await call.answer()


@router.callback_query(F.data == "admin:update:no")
async def cancel_update(call: CallbackQuery):
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


@router.message(F.text == BTN_BACK)
async def admin_back(message: types.Message, db: AsyncSession, state: FSMContext):
    await state.clear()
    from .start import get_menu_keyboard
    lang = await UserService(db).get_lang(message.from_user.id)
    await message.answer(i18n.get_text("start", lang), reply_markup=get_menu_keyboard(lang, is_admin=True))


# ─── Give Diamonds Flow ───

@router.message(F.text == BTN_GIVE_DIAMONDS)
async def give_diamonds_start(message: types.Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    await message.answer(
        "💎 <b>Give Diamonds</b>\n\nEnter user ID:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="❌ Cancel", callback_data="admin:give:cancel")
        ]]),
    )
    await state.set_state(GiveDiamondsStates.waiting_for_user_id)


@router.message(StateFilter(GiveDiamondsStates.waiting_for_user_id))
async def give_diamonds_user_id(message: types.Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    if not message.text.strip().isdigit():
        await message.answer("⚠️ Please enter a valid numeric user ID.")
        return
    user_id = int(message.text.strip())
    async with get_db() as db:
        user = await UserService(db).get_user(user_id)
    if not user:
        await message.answer(f"❌ User <code>{user_id}</code> not found.")
        return
    await state.update_data(user_id=user_id, user_name=user.name)
    await message.answer(
        f"👤 <b>{user.name}</b> (<code>{user_id}</code>)\n"
        f"💎 Current diamonds: <code>{user.diamonds}</code>\n\n"
        f"Enter diamond count to give:"
    )
    await state.set_state(GiveDiamondsStates.waiting_for_count)


@router.message(StateFilter(GiveDiamondsStates.waiting_for_count))
async def give_diamonds_count(message: types.Message, state: FSMContext, bot: Bot):
    if not is_admin(message.from_user.id):
        return
    text = message.text.strip()
    if not text.isdigit() or int(text) <= 0:
        await message.answer("⚠️ Please enter a positive number.")
        return
    count = int(text)
    data = await state.get_data()
    user_id, user_name = data["user_id"], data["user_name"]

    async with get_db() as db:
        service = UserService(db)
        await service.add_diamonds(user_id, count, record_payment=False)
        lang = await service.get_lang(user_id)

    try:
        await bot.send_message(user_id, i18n.get_text("admin-gift", lang).format(count=count))
    except Exception:
        pass

    await state.clear()
    await message.answer(
        f"✅ <b>Done!</b>\n\n👤 {user_name} (<code>{user_id}</code>)\n💎 +{count} diamonds",
        reply_markup=get_admin_keyboard(),
    )


@router.callback_query(F.data == "admin:give:cancel")
async def give_cancel(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        await call.answer()
        return
    await state.clear()
    await call.message.edit_text("Cancelled.")
    await call.answer()
