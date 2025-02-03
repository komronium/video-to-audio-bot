from datetime import datetime
from asyncio import sleep
from aiogram import types, Router, F
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from sqlalchemy.ext.asyncio import AsyncSession

from config import settings
from services.user_service import UserService
from states.post import PostStates

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


@router.message(StateFilter(PostStates.waiting_for_post))
async def process_post_content(message: types.Message, state: FSMContext, db: AsyncSession):
    if message.from_user.id == settings.ADMIN_ID:
        user_service = UserService(db)
        users = await user_service.get_all_users(exclude_admin=True)
        total_users = await user_service.total_users(exclude_admin=True)

        successful, failed = 0, 0
        stats_message = (
            "<b>📊 Post Sending Statistics:</b>\n\n"
            "Successful: <b>{successful}</b>\n"
            "Failed: <b>{failed}</b>\n"
            f"Total users: <b>{total_users}</b>\n"
            "Time: <b>{time}</b>"
        )

        processing_msg = await  message.answer(stats_message.format(
            successful=successful,
            failed=failed,
            time=datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        ))

        for user in users:
            try:
                await message.copy_to(user.user_id)
                successful += 1
            except Exception as e:
                failed += 1

            await processing_msg.edit_text(stats_message.format(
                successful=successful,
                failed=failed,
                time=datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            ))

            if (failed + successful) % 10 == 0:
                await sleep(2)

        await state.clear()


@router.callback_query(F.data == 'cancel_post')
async def cancel_post(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text("Post creation cancelled.")
    await callback.answer()
