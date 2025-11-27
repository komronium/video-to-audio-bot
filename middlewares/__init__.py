from aiogram import Dispatcher

from .throttling import ThrottlingMiddleware
from .database import DatabaseMiddleware


def setup_middlewares(dp: Dispatcher):
    dp.message.middleware(DatabaseMiddleware())
    dp.message.middleware(ThrottlingMiddleware())
