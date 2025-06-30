from datetime import datetime
from asyncio import sleep
from aiogram import types, Router, F, Bot
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from sqlalchemy.ext.asyncio import AsyncSession

from config import settings
from handlers.start import get_language_keyboard
from handlers.video import get_buy_more_keyboard
from services.user_service import UserService
from states.post import PostStates
from utils.i18n import i18n

router = Router()


def get_post_creation_keyboard():
    keyboard = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="❌ Cancel", callback_data="cancel_post")
    ]])
    return keyboard


@router.message(Command('post'))
async def create_post(message: types.Message, state: FSMContext):
    if message.from_user.id == settings.ADMIN_ID:
        await message.reply(
            "Please send the post content you want to share with subscribers.",
            reply_markup=get_post_creation_keyboard()
        )
        await state.set_state(PostStates.waiting_for_post)
        return


@router.message(Command('postlang'))
async def post_diamonds(message: types.Message, db: AsyncSession, bot: Bot):
    if message.from_user.id == settings.ADMIN_ID:
        user_service = UserService(db)
        users = await user_service.get_all_users(exclude_admin=True)
        total_users = await user_service.total_users(exclude_admin=True)

        successful, failed = 0, 0
        start_time = datetime.now()
        stats_message = (
            "<b>📊 Post Sending Statistics:</b>\n\n"
            "Successful: <b>{successful}</b>\n"
            "Failed: <b>{failed}</b>\n"
            f"Total users: <b>{total_users}</b>\n"
            "Time: <code>{time}</code>"
        )

        processing_msg = await message.answer(stats_message.format(
            successful=successful,
            failed=failed,
            time='00:00:00'
        ))

        for user in users:
            try:
                await bot.send_message(
                    user.user_id,
                    i18n.get_text('choose_language'),
                    reply_markup=get_language_keyboard()
                )
                successful += 1
            except Exception:
                failed += 1

            time = datetime.now() - start_time
            hours: int = time.seconds // 3600
            minutes = time.seconds % 3600 // 60
            seconds = time.seconds % 60
            await processing_msg.edit_text(stats_message.format(
                successful=successful,
                failed=failed,
                time='{:02d}:{:02d}:{:02d}'.format(hours, minutes, seconds)
            ))

            if (failed + successful) % 10 == 0:
                await sleep(2)


@router.message(StateFilter(PostStates.waiting_for_post))
async def process_post_content(message: types.Message, state: FSMContext, db: AsyncSession):
    if message.from_user.id == settings.ADMIN_ID:
        user_service = UserService(db)
        users = await user_service.get_all_users(exclude_admin=True)
        total_users = await user_service.total_users(exclude_admin=True)

        successful, failed = 0, 0
        start_time = datetime.now()
        stats_message = (
            "<b>📊 Post Sending Statistics:</b>\n\n"
            "Successful: <b>{successful}</b>\n"
            "Failed: <b>{failed}</b>\n"
            f"Total users: <b>{total_users}</b>\n"
            "Time: <code>{time}</code>"
        )

        processing_msg = await message.answer(stats_message.format(
            successful=successful,
            failed=failed,
            time='00:00:00'
        ))

        for user in users:
            try:
                await message.copy_to(user.user_id)
                successful += 1
            except Exception:
                failed += 1

            time = datetime.now() - start_time
            hours: int = time.seconds // 3600
            minutes = time.seconds % 3600 // 60
            seconds = time.seconds % 60
            await processing_msg.edit_text(stats_message.format(
                successful=successful,
                failed=failed,
                time='{:02d}:{:02d}:{:02d}'.format(hours, minutes, seconds)
            ))

            if (failed + successful) % 10 == 0:
                await sleep(2)

        await state.clear()


@router.callback_query(F.data == 'cancel_post')
async def cancel_post(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text("Post creation cancelled.")
    await callback.answer()
