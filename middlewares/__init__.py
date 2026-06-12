from aiogram import Dispatcher

from .throttling import ThrottlingMiddleware
from .subscription import SubscriptionMiddleware
from .database import DatabaseMiddleware


def setup_middlewares(dp: Dispatcher):
    # Throttling first: flooded messages must be dropped before opening a DB session
    dp.message.middleware(ThrottlingMiddleware())
    dp.message.middleware(DatabaseMiddleware())
    # dp.message.middleware(SubscriptionMiddleware())
