from aiogram import Dispatcher

from .throttling import ThrottlingMiddleware
from .subscription import SubscriptionMiddleware
from .database import DatabaseMiddleware


def setup_middlewares(dp: Dispatcher):
    dp.message.middleware(ThrottlingMiddleware())
    dp.message.middleware(SubscriptionMiddleware())
    dp.message.middleware(DatabaseMiddleware())
