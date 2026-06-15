"""Segmented broadcast flow.

UX:
    /broadcast or admin button
      ↓
    pick segment (or 🌍 → pick language)
      ↓
    show audience size, ask for message content
      ↓
    preview message back to admin → confirm/cancel
      ↓
    send with progress (every 50 messages), final stats
"""

from asyncio import sleep
from datetime import datetime

from aiogram import F, Router, types
from aiogram.exceptions import TelegramAPIError, TelegramRetryAfter
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy.ext.asyncio import AsyncSession

from config import settings
from database.session import get_db
from services.segments import SEGMENTS, resolve_segment
from services.user_service import UserService
from states.post import PostStates
from utils.i18n import i18n

router = Router()

# Telegram's per-user message limit is ~30/sec — sleep keeps us comfortably
# under it. For broadcasts we also batch-update progress every 50 messages.
SEND_SLEEP = 0.04
PROGRESS_EVERY = 50


def is_admin(user_id: int) -> bool:
    return user_id == settings.ADMIN_ID


CANCEL_KB = InlineKeyboardMarkup(
    inline_keyboard=[[InlineKeyboardButton(text="❌ Cancel", callback_data="post:cancel")]]
)


def _segment_keyboard() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    for key, label in SEGMENTS.items():
        b.button(text=label, callback_data=f"post:seg:{key}")
    b.button(text="❌ Cancel", callback_data="post:cancel")
    b.adjust(1)
    return b.as_markup()


def _lang_keyboard() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    for lang in i18n.LANGUAGES:
        b.button(text=i18n.get_text("lang", lang), callback_data=f"post:seg:lang:{lang}")
    b.button(text="⬅️ Back", callback_data="post:back-to-segments")
    b.adjust(2)
    return b.as_markup()


def _confirm_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🚀 Send now", callback_data="post:confirm")],
            [InlineKeyboardButton(text="❌ Cancel", callback_data="post:cancel")],
        ]
    )


def _fmt_elapsed(start: datetime) -> str:
    secs = int((datetime.now() - start).total_seconds())
    return f"{secs // 3600:02d}:{(secs % 3600) // 60:02d}:{secs % 60:02d}"


# ─── Entry points ─────────────────────────────────────────────────────────


@router.message(Command("broadcast"), F.from_user.id == settings.ADMIN_ID)
@router.message(Command("post"), F.from_user.id == settings.ADMIN_ID)
async def broadcast_entry(message: Message, state: FSMContext):
    await state.clear()
    await message.answer(
        "📣 <b>Broadcast</b>\n\nWho should receive this message?",
        reply_markup=_segment_keyboard(),
    )
    await state.set_state(PostStates.choosing_segment)


@router.callback_query(F.data == "post:cancel")
async def post_cancel(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        await call.answer()
        return
    await state.clear()
    try:
        await call.message.edit_text("Broadcast cancelled.")
    except Exception:
        pass
    await call.answer()


@router.callback_query(F.data == "post:back-to-segments", StateFilter(PostStates.choosing_segment))
async def post_back_to_segments(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        await call.answer()
        return
    await call.message.edit_text(
        "📣 <b>Broadcast</b>\n\nWho should receive this message?",
        reply_markup=_segment_keyboard(),
    )
    await call.answer()


# ─── Step 1: pick segment ─────────────────────────────────────────────────


@router.callback_query(F.data.startswith("post:seg:"), StateFilter(PostStates.choosing_segment))
async def post_pick_segment(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        await call.answer()
        return
    seg = call.data[len("post:seg:"):]
    if seg == "by_lang":
        await call.message.edit_text(
            "🌍 <b>Pick a language</b>", reply_markup=_lang_keyboard()
        )
        await call.answer()
        return

    async with get_db() as db:
        result = await resolve_segment(db, seg)

    if not result.user_ids:
        await call.message.edit_text(
            f"⚠️ <b>{result.label}</b> matches 0 users.",
            reply_markup=_segment_keyboard(),
        )
        await call.answer()
        return

    await state.update_data(segment=seg, count=len(result.user_ids), label=result.label)
    await call.message.edit_text(
        f"📣 <b>Segment selected</b>\n\n"
        f"{result.label}\n"
        f"<b>Audience:</b> {len(result.user_ids):,} users\n\n"
        f"Now send the post content (text, photo, video, etc.).",
        reply_markup=CANCEL_KB,
    )
    await state.set_state(PostStates.waiting_for_post)
    await call.answer()


# ─── Step 2: receive content ──────────────────────────────────────────────


@router.message(StateFilter(PostStates.waiting_for_post), F.from_user.id == settings.ADMIN_ID)
async def post_receive_content(message: Message, state: FSMContext):
    data = await state.get_data()
    # Stash the message reference so we can re-copy it on confirm. We don't
    # store the content itself — copy_to() handles every media type natively.
    await state.update_data(content_chat_id=message.chat.id, content_message_id=message.message_id)

    preview = (
        "🎬 <b>Preview</b>\n\n"
        f"Segment: <b>{data['label']}</b>\n"
        f"Audience: <b>{data['count']:,}</b>\n\n"
        "Send the broadcast?"
    )
    await message.answer(preview, reply_markup=_confirm_keyboard())
    await state.set_state(PostStates.confirming)


# ─── Step 3: send ─────────────────────────────────────────────────────────


@router.callback_query(F.data == "post:confirm", StateFilter(PostStates.confirming))
async def post_confirm(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        await call.answer()
        return
    data = await state.get_data()
    await state.clear()
    await call.answer("Starting…")

    # Re-resolve so the audience is fresh (could've shifted since pick)
    async with get_db() as db:
        result = await resolve_segment(db, data["segment"])
    user_ids = result.user_ids
    total = len(user_ids)

    if total == 0:
        await call.message.edit_text("⚠️ Segment is empty now — nothing sent.")
        return

    status = await call.message.edit_text(
        _progress_text(result.label, 0, 0, 0, total, datetime.now())
    )
    sent = failed = blocked = 0
    start = datetime.now()
    # Batch newly-blocked ids and persist them in one transaction at the end,
    # so a 9k-user broadcast doesn't pay 9k tiny UPDATEs interleaved with sends.
    newly_blocked: list[int] = []

    for i, uid in enumerate(user_ids, start=1):
        try:
            await call.bot.copy_message(
                chat_id=uid,
                from_chat_id=data["content_chat_id"],
                message_id=data["content_message_id"],
            )
            sent += 1
        except TelegramRetryAfter as e:
            await sleep(e.retry_after)
            try:
                await call.bot.copy_message(
                    chat_id=uid,
                    from_chat_id=data["content_chat_id"],
                    message_id=data["content_message_id"],
                )
                sent += 1
            except TelegramAPIError as e2:
                if _is_blocked(e2):
                    blocked += 1
                    newly_blocked.append(uid)
                else:
                    failed += 1
        except TelegramAPIError as e:
            if _is_blocked(e):
                blocked += 1
                newly_blocked.append(uid)
            else:
                failed += 1
        except Exception:
            failed += 1

        if i % PROGRESS_EVERY == 0:
            try:
                await status.edit_text(
                    _progress_text(result.label, sent, failed, blocked, total, start)
                )
            except TelegramAPIError:
                pass
        await sleep(SEND_SLEEP)

    if newly_blocked:
        async with get_db() as db:
            service = UserService(db)
            for uid in newly_blocked:
                await service.mark_blocked(uid)

    try:
        await status.edit_text(
            _progress_text(result.label, sent, failed, blocked, total, start, done=True)
        )
    except TelegramAPIError:
        pass


def _progress_text(
    label: str,
    sent: int,
    failed: int,
    blocked: int,
    total: int,
    start: datetime,
    done: bool = False,
) -> str:
    icon = "✅" if done else "📤"
    title = "Broadcast complete" if done else "Broadcasting…"
    return (
        f"{icon} <b>{title}</b>\n\n"
        f"<b>Segment:</b> {label}\n"
        f"<b>Sent:</b> {sent:,} / {total:,}\n"
        f"<b>Blocked/dead:</b> {blocked:,}\n"
        f"<b>Other failures:</b> {failed:,}\n"
        f"<b>Elapsed:</b> <code>{_fmt_elapsed(start)}</code>"
    )


def _is_blocked(e: TelegramAPIError) -> bool:
    err = str(e).lower()
    return "blocked" in err or "deactivated" in err or "chat not found" in err
