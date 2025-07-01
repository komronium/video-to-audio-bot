from aiogram import types, Router
from aiogram.filters import Command
from aiogram.exceptions import TelegramAPIError


router = Router()


@router.message(Command("help"))
async def command_help(message: types.Message):
    text = (
        "🆘 <b>Help Menu</b>\n\n"
        "Here are the available commands:\n\n"
        "🔹 /start - Start the bot\n"
        "🔹 /help - Get help information\n"
        "🔹 /stats - View bot statistics\n"
        "🔹 /profile - View your profile\n"
        "🔹 /top - View the top active users\n\n"
        "If you have any questions, feel free to ask! 😊"
    )

    try:
        await message.answer(text)
    except TelegramAPIError:
        await message.answer("Sorry, something went wrong. Please try again later.")
