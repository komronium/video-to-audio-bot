import asyncio
from logging import basicConfig, INFO

from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.client.telegram import TelegramAPIServer

from config import settings
from middlewares import setup_middlewares
from handlers import setup_handlers
from utils.set_commands import set_default_commands


async def on_startup(bot: Bot):
    await bot.send_message(settings.GROUP_ID, "<b>✅ THE BOT IS UP!</b>")


async def on_shutdown(bot: Bot):
    await bot.send_message(settings.GROUP_ID, "<b>❌ THE BOT HAS BEEN SUSPENDED!</b>")
    await bot.session.close()


async def main():
    basicConfig(level=INFO)
    local_server = TelegramAPIServer.from_base('http://localhost:8081')
    session = AiohttpSession(api=local_server)

    bot = Bot(
        token=settings.BOT_TOKEN,
        session=session,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML)
    )

    dp = Dispatcher()

    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)

    setup_middlewares(dp)
    setup_handlers(dp)

    await set_default_commands(bot)
    await dp.start_polling(bot)


if __name__ == '__main__':
    asyncio.run(main())
