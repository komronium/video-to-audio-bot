from aiogram import Bot
from aiogram.types import BotCommand


async def set_default_commands(bot: Bot):
    await bot.set_my_commands([
        BotCommand(command="start", description="Start the bot"),
        BotCommand(command="help", description="Get help information"),
        BotCommand(command="stats", description="View bot statistics"),
        BotCommand(command="profile", description="View your profile"),
        BotCommand(command="settings", description="Manage your settings"),
    ])
