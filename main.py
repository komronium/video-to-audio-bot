import asyncio
import os
import sys
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


PID_FILE = "/tmp/video-to-audio-bot.pid"


def check_pid_lock():
    if os.path.exists(PID_FILE):
        with open(PID_FILE) as f:
            old_pid = int(f.read().strip())
        if os.path.exists(f"/proc/{old_pid}"):
            print(f"Bot already running (PID {old_pid}). Killing old instance...")
            os.kill(old_pid, 9)
    with open(PID_FILE, "w") as f:
        f.write(str(os.getpid()))


async def main():
    basicConfig(level=INFO)
    check_pid_lock()
    local_server = TelegramAPIServer.from_base('http://localhost:8081')
    session = AiohttpSession(api=local_server, timeout=300)

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
