"""Admin-only promo creation flow.

UX flow (each step has a Cancel button so the admin can bail out cleanly):

    /promo
      ↓
    [type chooser] — 2x diamonds · monthly % off · lifetime % off
      ↓
    [value]        — multiplier (1.5-5) or percent (1-90)
      ↓
    [duration]     — 6h · 12h · 24h · 48h · custom hours
      ↓
    [label]        — short human title (auto-suggested)
      ↓
    [preview]      — confirm or cancel
      ↓
    saved to Redis with TTL
"""

from datetime import datetime, timedelta

from aiogram import F, Router, types
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)
from aiogram.utils.keyboard import InlineKeyboardBuilder

from config import settings
from services.promo import (
    Promo,
    clear_promo,
    fmt_countdown,
    get_active_promo,
    set_promo,
)
from states.promo import PromoStates

router = Router()


CANCEL_KB = InlineKeyboardMarkup(
    inline_keyboard=[[InlineKeyboardButton(text="❌ Cancel", callback_data="promo:cancel")]]
)


def is_admin(user_id: int) -> bool:
    return user_id == settings.ADMIN_ID


def _type_keyboard() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="💎 2× Diamonds", callback_data="promo:type:2x_diamonds")
    b.button(text="📅 Monthly % off", callback_data="promo:type:monthly_discount")
    b.button(text="👑 Lifetime % off", callback_data="promo:type:lifetime_discount")
    b.button(text="❌ Cancel", callback_data="promo:cancel")
    b.adjust(1)
    return b.as_markup()


def _duration_keyboard() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    for h in (6, 12, 24, 48, 72):
        b.button(text=f"⏳ {h}h", callback_data=f"promo:dur:{h}")
    b.button(text="✏️ Custom", callback_data="promo:dur:custom")
    b.button(text="❌ Cancel", callback_data="promo:cancel")
    b.adjust(2, 2, 1, 1)
    return b.as_markup()


def _confirm_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✅ Activate", callback_data="promo:confirm")],
            [InlineKeyboardButton(text="❌ Cancel", callback_data="promo:cancel")],
        ]
    )


def _default_label(ptype: str, value: int) -> str:
    if ptype == "2x_diamonds":
        return f"{value}× diamonds — limited time"
    if ptype == "monthly_discount":
        return f"{value}% off Monthly Premium"
    return f"{value}% off Lifetime Premium"


# ─── Entry: show current state or start the flow ──────────────────────────


@router.message(Command("promo"), F.from_user.id == settings.ADMIN_ID)
async def promo_entry(message: Message, state: FSMContext):
    await state.clear()
    promo = await get_active_promo()
    if promo:
        text = (
            "🎁 <b>Active promo</b>\n\n"
            f"<b>Type:</b> {promo.type}\n"
            f"<b>Value:</b> {promo.value}\n"
            f"<b>Label:</b> {promo.label}\n"
            f"<b>Ends in:</b> {fmt_countdown(promo.seconds_left())}\n\n"
            "Cancel it to create a new one."
        )
        kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="🛑 Cancel active promo", callback_data="promo:clear")],
                [InlineKeyboardButton(text="❌ Close", callback_data="promo:cancel")],
            ]
        )
        await message.answer(text, reply_markup=kb)
        return
    await message.answer(
        "🎁 <b>Create a promo</b>\n\nChoose the promo type:",
        reply_markup=_type_keyboard(),
    )
    await state.set_state(PromoStates.choosing_type)


@router.callback_query(F.data == "promo:cancel")
async def promo_cancel(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        await call.answer()
        return
    await state.clear()
    try:
        await call.message.edit_text("Cancelled.")
    except Exception:
        pass
    await call.answer()


@router.callback_query(F.data == "promo:clear")
async def promo_clear(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        await call.answer()
        return
    await clear_promo()
    await call.message.edit_text("🛑 Active promo cancelled.")
    await call.answer("Cleared")


# ─── Step 1: type ─────────────────────────────────────────────────────────


@router.callback_query(F.data.startswith("promo:type:"), StateFilter(PromoStates.choosing_type))
async def promo_pick_type(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        await call.answer()
        return
    ptype = call.data.split(":")[2]
    await state.update_data(ptype=ptype)
    if ptype == "2x_diamonds":
        prompt = (
            "💎 <b>2× Diamonds</b>\n\n"
            "Enter the multiplier (2-5).\n"
            "Example: <code>2</code> → users get double the diamonds they buy."
        )
    else:
        prompt = (
            "🏷 <b>Discount %</b>\n\n"
            "Enter a number from 5 to 80.\n"
            "Example: <code>30</code> = 30% off."
        )
    await call.message.edit_text(prompt, reply_markup=CANCEL_KB)
    await state.set_state(PromoStates.entering_value)
    await call.answer()


# ─── Step 2: value ────────────────────────────────────────────────────────


@router.message(StateFilter(PromoStates.entering_value), F.from_user.id == settings.ADMIN_ID)
async def promo_value(message: Message, state: FSMContext):
    text = (message.text or "").strip()
    if not text.isdigit():
        await message.reply("⚠️ Enter a whole number.", reply_markup=CANCEL_KB)
        return
    value = int(text)
    data = await state.get_data()
    ptype = data["ptype"]
    if ptype == "2x_diamonds":
        if not 2 <= value <= 5:
            await message.reply("⚠️ Multiplier must be 2-5.", reply_markup=CANCEL_KB)
            return
    else:
        if not 5 <= value <= 80:
            await message.reply("⚠️ Discount must be 5-80.", reply_markup=CANCEL_KB)
            return
    await state.update_data(value=value)
    await message.answer("⏳ <b>Duration</b>\n\nHow long should the promo last?", reply_markup=_duration_keyboard())
    await state.set_state(PromoStates.entering_hours)


# ─── Step 3: duration ─────────────────────────────────────────────────────


@router.callback_query(F.data.startswith("promo:dur:"), StateFilter(PromoStates.entering_hours))
async def promo_duration(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        await call.answer()
        return
    arg = call.data.split(":")[2]
    if arg == "custom":
        await call.message.edit_text(
            "✏️ Enter custom duration in hours (1-168):", reply_markup=CANCEL_KB
        )
        await call.answer()
        return
    hours = int(arg)
    await state.update_data(hours=hours)
    await _ask_label(call.message, state, edit=True)
    await call.answer()


@router.message(StateFilter(PromoStates.entering_hours), F.from_user.id == settings.ADMIN_ID)
async def promo_custom_hours(message: Message, state: FSMContext):
    text = (message.text or "").strip()
    if not text.isdigit():
        await message.reply("⚠️ Enter a number of hours.", reply_markup=CANCEL_KB)
        return
    hours = int(text)
    if not 1 <= hours <= 168:
        await message.reply("⚠️ Must be 1-168 hours (1 week max).", reply_markup=CANCEL_KB)
        return
    await state.update_data(hours=hours)
    await _ask_label(message, state, edit=False)


async def _ask_label(target, state: FSMContext, edit: bool):
    data = await state.get_data()
    suggested = _default_label(data["ptype"], data["value"])
    text = (
        "🏷 <b>Label</b>\n\n"
        "What should users see in the promo banner?\n"
        f"Send a short title or just send <code>ok</code> to use:\n<code>{suggested}</code>"
    )
    if edit:
        try:
            await target.edit_text(text, reply_markup=CANCEL_KB)
            await state.set_state(PromoStates.entering_label)
            return
        except Exception:
            pass
    await target.answer(text, reply_markup=CANCEL_KB)
    await state.set_state(PromoStates.entering_label)


# ─── Step 4: label ────────────────────────────────────────────────────────


@router.message(StateFilter(PromoStates.entering_label), F.from_user.id == settings.ADMIN_ID)
async def promo_label(message: Message, state: FSMContext):
    text = (message.text or "").strip()
    data = await state.get_data()
    if text.lower() in ("ok", "/ok", "default"):
        label = _default_label(data["ptype"], data["value"])
    else:
        label = text[:80]
    await state.update_data(label=label)

    expires_at = datetime.now() + timedelta(hours=data["hours"])
    preview = (
        "🎁 <b>Preview</b>\n\n"
        f"<b>Type:</b> {data['ptype']}\n"
        f"<b>Value:</b> {data['value']}\n"
        f"<b>Duration:</b> {data['hours']} hours\n"
        f"<b>Ends:</b> {expires_at:%Y-%m-%d %H:%M}\n"
        f"<b>Label:</b> {label}\n\n"
        "Activate?"
    )
    await message.answer(preview, reply_markup=_confirm_keyboard())
    await state.set_state(PromoStates.confirming)


# ─── Step 5: confirm ──────────────────────────────────────────────────────


@router.callback_query(F.data == "promo:confirm", StateFilter(PromoStates.confirming))
async def promo_save(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        await call.answer()
        return
    data = await state.get_data()
    expires_at = datetime.now() + timedelta(hours=data["hours"])
    promo = Promo(
        type=data["ptype"],
        value=data["value"],
        expires_at=expires_at,
        label=data["label"],
        created_by=call.from_user.id,
    )
    ok = await set_promo(promo)
    await state.clear()
    if ok:
        await call.message.edit_text(
            f"✅ <b>Promo live</b>\n\n"
            f"🎁 {promo.label}\n"
            f"⏳ Ends in: {fmt_countdown(promo.seconds_left())}\n\n"
            f"Users will see the banner in the Premium menu."
        )
    else:
        await call.message.edit_text("❌ Failed to activate (Redis unreachable?).")
    await call.answer()
