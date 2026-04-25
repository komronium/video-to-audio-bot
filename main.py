import asyncio
import logging
import os
import signal

from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.client.telegram import TelegramAPIServer

from config import settings
from database.models import create_tables
from middlewares import setup_middlewares
from handlers import setup_handlers
from services.redis_queue import queue_manager
from utils.set_commands import set_default_commands

PID_FILE = "/tmp/video-to-audio-bot.pid"


def check_pid_lock():
    if os.path.exists(PID_FILE):
        try:
            with open(PID_FILE) as f:
                old_pid = int(f.read().strip())
            if os.path.exists(f"/proc/{old_pid}"):
                logging.info(f"Stopping old instance (PID {old_pid})...")
                os.kill(old_pid, signal.SIGTERM)
                # Give it 3 seconds to exit gracefully before forcing
                import time
                for _ in range(6):
                    time.sleep(0.5)
                    if not os.path.exists(f"/proc/{old_pid}"):
                        break
                else:
                    os.kill(old_pid, signal.SIGKILL)
        except (ValueError, ProcessLookupError, FileNotFoundError):
            pass
    with open(PID_FILE, "w") as f:
        f.write(str(os.getpid()))


async def on_startup(bot: Bot):
    await create_tables()
    await queue_manager.clear_queue()
    await bot.send_message(settings.GROUP_ID, "<b>✅ THE BOT IS UP!</b>")


async def on_shutdown(bot: Bot):
    await bot.send_message(settings.GROUP_ID, "<b>❌ THE BOT HAS BEEN SUSPENDED!</b>")
    if os.path.exists(PID_FILE):
        os.remove(PID_FILE)


async def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    check_pid_lock()

    local_server = TelegramAPIServer.from_base("http://localhost:8081")
    session = AiohttpSession(api=local_server, timeout=300)

    bot = Bot(
        token=settings.BOT_TOKEN,
        session=session,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )

    dp = Dispatcher()
    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)

    setup_middlewares(dp)
    setup_handlers(dp)

    await set_default_commands(bot)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
