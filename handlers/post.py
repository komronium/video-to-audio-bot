from datetime import datetime
from asyncio import sleep

from aiogram import types, Router, F
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext

from config import settings
from handlers.start import get_language_keyboard
from services.user_service import UserService
from states.post import PostStates
from utils.i18n import i18n

router = Router()

_STATS_TEMPLATE = (
    "<b>📊 Post Sending Statistics:</b>\n\n"
    "Successful: <b>{successful}</b>\n"
    "Failed: <b>{failed}</b>\n"
    "Total users: <b>{total}</b>\n"
    "Time: <code>{time}</code>"
)


def _fmt_elapsed(start: datetime) -> str:
    secs = int((datetime.now() - start).total_seconds())
    return f"{secs // 3600:02d}:{(secs % 3600) // 60:02d}:{secs % 60:02d}"


async def _broadcast(message: types.Message, users: list, send_fn, total: int):
    successful, failed = 0, 0
    start = datetime.now()
    status_msg = await message.answer(
        _STATS_TEMPLATE.format(successful=0, failed=0, total=total, time="00:00:00")
    )
    for i, user in enumerate(users, start=1):
        try:
            await send_fn(user)
            successful += 1
        except Exception:
            failed += 1
        if i % 10 == 0:
            await status_msg.edit_text(
                _STATS_TEMPLATE.format(
                    successful=successful, failed=failed,
                    total=total, time=_fmt_elapsed(start),
                )
            )
            await sleep(2)
    await status_msg.edit_text(
        _STATS_TEMPLATE.format(
            successful=successful, failed=failed,
            total=total, time=_fmt_elapsed(start),
        )
    )


async def create_post_internal(message: types.Message, state: FSMContext):
    if message.from_user.id != settings.ADMIN_ID:
        return
    await message.reply(
        "Please send the post content to broadcast to all subscribers.",
        reply_markup=types.InlineKeyboardMarkup(inline_keyboard=[[
            types.InlineKeyboardButton(text="❌ Cancel", callback_data="cancel_post")
        ]]),
    )
    await state.set_state(PostStates.waiting_for_post)


async def postlang_internal(message: types.Message, db, bot):
    if message.from_user.id != settings.ADMIN_ID:
        return
    service = UserService(db)
    users = await service.get_all_users(exclude_admin=True)
    total = await service.total_users(exclude_admin=True)

    async def send(user):
        await bot.send_message(
            user.user_id,
            i18n.get_text("choose_language"),
            reply_markup=get_language_keyboard(),
        )

    await _broadcast(message, users, send, total)


@router.message(StateFilter(PostStates.waiting_for_post))
async def process_post_content(message: types.Message, state: FSMContext, db):
    if message.from_user.id != settings.ADMIN_ID:
        return
    service = UserService(db)
    users = await service.get_all_users(exclude_admin=True)
    total = await service.total_users(exclude_admin=True)

    async def send(user):
        await message.copy_to(user.user_id)

    await _broadcast(message, users, send, total)
    await state.clear()


@router.callback_query(F.data == "cancel_post")
async def cancel_post(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text("Post creation cancelled.")
    await callback.answer()
