from aiogram import Dispatcher

from .throttling import ThrottlingMiddleware
from .subscription import SubscriptionMiddleware
from .database import DatabaseMiddleware
from .i18n import I18nMiddleware


def setup_middlewares(dp: Dispatcher):
    dp.message.middleware(DatabaseMiddleware())
    dp.message.middleware(ThrottlingMiddleware())
    dp.message.middleware(SubscriptionMiddleware())
    dp.message.middleware(I18nMiddleware())
